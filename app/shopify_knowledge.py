"""Build the knowledge base from a real Shopify store: products, legal policies and content pages.

Needs read-only scopes: read_products, read_content (pages) and read_legal_policies (policies).
"""
import html
import re

from app.knowledge import MAX_CHARS, Piece
from app.shopify.client import ShopifyClient

PRODUCTS = """query($after: String) { products(first: 50, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { handle title description productType
    priceRangeV2 { minVariantPrice { amount currencyCode } }
    variants(first: 50) { nodes { title } } } } }"""

POLICIES = """{ shop { name shopPolicies { title body type } } }"""

PAGES = """{ pages(first: 50) { nodes { handle title body } } }"""

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</(p|div|li|h[1-6])>|<br\s*/?>", re.I)


def html_to_text(raw: str) -> str:
    text = _BLOCK.sub("\n\n", raw or "")
    text = html.unescape(_TAG.sub("", text))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _split(source: str, ref: str, title: str, text: str) -> list[Piece]:
    pieces, buf = [], ""
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if buf and len(buf) + len(para) > MAX_CHARS:
            pieces.append(Piece(source, ref, title, buf))
            buf = ""
        buf = f"{buf}\n\n{para}".strip()
    if buf:
        pieces.append(Piece(source, ref, title, buf))
    return pieces


def load_from_shopify(client: ShopifyClient) -> list[Piece]:
    pieces: list[Piece] = []
    after = None
    while True:
        page = client.graphql(PRODUCTS, {"after": after})["products"]
        for p in page["nodes"]:
            price = p["priceRangeV2"]["minVariantPrice"]
            variants = [v["title"] for v in p["variants"]["nodes"] if v["title"] != "Default Title"]
            lines = [p["title"], p.get("description") or "", f"Price from {price['amount']} {price['currencyCode']}"]
            if variants:
                lines.append("Options: " + ", ".join(variants))
            pieces.append(Piece("product", p["handle"], p["title"], "\n".join(x for x in lines if x)))
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    for pol in client.graphql(POLICIES)["shop"]["shopPolicies"]:
        pieces += _split("policy", pol["type"], pol["title"], html_to_text(pol["body"]))
    for pg in client.graphql(PAGES)["pages"]["nodes"]:
        pieces += _split("page", pg["handle"], pg["title"], html_to_text(pg["body"]))
    return pieces
