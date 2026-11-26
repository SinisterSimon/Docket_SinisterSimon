"""The tools the agent may call. Each returns plain text for the model and a list of sources,
so every fact in a reply can be traced to where it came from.

Privacy rule: order details are only returned when the email on the order matches the sender.
Otherwise the tool says it found nothing, so a stranger can't fish for someone else's order.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import knowledge
from app.llm.embeddings import Embedder
from app.store import Store


@dataclass
class ToolResult:
    text: str
    sources: list[str] = field(default_factory=list)


@dataclass
class ToolBox:
    session: Session
    embedder: Embedder
    store: Store
    sender: str  # the customer's email, used for the order privacy check

    def search_knowledge(self, query: str) -> ToolResult:
        hits = knowledge.search(self.session, query, self.embedder, k=3)
        if not hits:
            return ToolResult("No matching store policy or product.")
        body = "\n\n".join(f"[{h.chunk.title}]\n{h.chunk.text}" for h in hits)
        return ToolResult(body, [h.chunk.title for h in hits])

    def order_status(self, order_number: str) -> ToolResult:
        order = self.store.order(order_number)
        if order is None or order.email.lower() != self.sender.lower():
            return ToolResult(f"No order {order_number} found for this customer's email.")
        tracking = "; ".join(f"{t.get('company') or 'Carrier'} {t.get('number', '')} {t.get('url', '')}".strip()
                             for t in order.tracking) or "none yet"
        text = (f"Order {order.name}, placed {order.created}. Payment: {order.financial}. "
                f"Fulfilment: {order.fulfillment}. Items: {', '.join(order.items)}. Tracking: {tracking}.")
        return ToolResult(text, [f"Order {order.name}"])

    def check_stock(self, product: str) -> ToolResult:
        stock = self.store.stock(product)
        if stock is None:
            return ToolResult(f"No product matching '{product}'.")
        parts = [f"{opt}: {'in stock' if qty > 0 else 'sold out'}" for opt, qty in stock.variants.items()]
        return ToolResult(f"{stock.product}. " + "; ".join(parts) + ".", [f"Stock: {stock.product}"])

    def call(self, name: str, args: dict) -> ToolResult:
        fn = {"search_knowledge": self.search_knowledge, "order_status": self.order_status,
              "check_stock": self.check_stock}.get(name)
        if fn is None:
            return ToolResult(f"Unknown tool {name!r}.")
        try:
            return fn(**args)
        except TypeError:
            return ToolResult(f"Wrong arguments for {name}: {args}.")


TOOL_SPEC = """Tools (call one at a time):
- search_knowledge(query): the store's shipping, returns, sizing, warranty and product pages.
- order_status(order_number): status, items and tracking for one of this customer's orders.
- check_stock(product): which sizes of a product are in stock (never exact unit counts)."""

ORDER_NUMBER = re.compile(r"#?\b(\d{4,6})\b")
