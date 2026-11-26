"""Live store data the agent can look up: orders and stock. Read-only.

Two backends with the same methods: the sample store (JSON files, used offline and in tests)
and a real Shopify store (Admin GraphQL API, read-only scopes).
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.shopify.client import ShopifyClient, client_from_env

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_store"


@dataclass(frozen=True)
class Order:
    name: str
    email: str
    created: str
    financial: str
    fulfillment: str
    tracking: list[dict]
    items: list[str]


@dataclass(frozen=True)
class Stock:
    product: str
    variants: dict[str, int]  # option -> units available


class Store(Protocol):
    def order(self, name: str) -> Order | None: ...
    def stock(self, product: str) -> Stock | None: ...


def _order_name(raw: str) -> str:
    return "#" + raw.strip().lstrip("#")


class SampleStore:
    def __init__(self, directory: Path = SAMPLE_DIR):
        self._orders = {o["name"]: Order(**o) for o in json.loads((directory / "orders.json").read_text())}
        self._products = json.loads((directory / "products.json").read_text())

    def order(self, name: str) -> Order | None:
        return self._orders.get(_order_name(name))

    def stock(self, product: str) -> Stock | None:
        q = product.lower().strip()
        for p in self._products:
            if q and (q in p["title"].lower() or q == p["handle"]):
                return Stock(p["title"], dict(p.get("stock", {})))
        return None


ORDER_QUERY = """query($q: String!) { orders(first: 1, query: $q) { nodes {
  name email createdAt displayFinancialStatus displayFulfillmentStatus
  fulfillments { trackingInfo { company number url } }
  lineItems(first: 20) { nodes { title quantity variantTitle } } } } }"""

STOCK_QUERY = """query($q: String!) { products(first: 1, query: $q) { nodes {
  title variants(first: 50) { nodes { title inventoryQuantity } } } } }"""


class ShopifyStore:
    def __init__(self, client: ShopifyClient):
        self._client = client

    def order(self, name: str) -> Order | None:
        nodes = self._client.graphql(ORDER_QUERY, {"q": f"name:{_order_name(name)}"})["orders"]["nodes"]
        if not nodes:
            return None
        o = nodes[0]
        items = [
            f"{li['quantity']} × {li['title']}" + (f" ({li['variantTitle']})" if li.get("variantTitle") else "")
            for li in o["lineItems"]["nodes"]
        ]
        tracking = [t for f in o["fulfillments"] for t in f["trackingInfo"]]
        return Order(o["name"], o.get("email") or "", o["createdAt"][:10], o["displayFinancialStatus"],
                     o["displayFulfillmentStatus"], tracking, items)

    def stock(self, product: str) -> Stock | None:
        safe = product.replace('"', "")
        nodes = self._client.graphql(STOCK_QUERY, {"q": f'title:"{safe}"'})["products"]["nodes"]
        if not nodes:
            return None
        p = nodes[0]
        return Stock(p["title"], {v["title"]: v["inventoryQuantity"] or 0 for v in p["variants"]["nodes"]})


def get_store() -> Store:
    client = client_from_env()
    return ShopifyStore(client) if client else SampleStore()
