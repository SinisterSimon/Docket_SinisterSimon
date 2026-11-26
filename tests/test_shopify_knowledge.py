from app.shopify_knowledge import html_to_text, load_from_shopify


class FakeClient:
    def graphql(self, query, variables=None):
        if "products" in query:
            return {"products": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [
                {"handle": "oxygen", "title": "Oxygen", "description": "Freeride board.", "productType": "",
                 "priceRangeV2": {"minVariantPrice": {"amount": "1025.0", "currencyCode": "EUR"}},
                 "variants": {"nodes": [{"title": "160 cm"}, {"title": "164W cm"}]}}]}}
        if "shopPolicies" in query:
            return {"shop": {"name": "S", "shopPolicies": [
                {"title": "Refund policy", "type": "REFUND_POLICY", "body": "<p>30 days.</p><p>Unused only.</p>"}]}}
        return {"pages": {"nodes": [{"handle": "faq", "title": "FAQ", "body": "<h2>Wax?</h2><p>Yes &amp; free.</p>"}]}}


def test_html_to_text_keeps_paragraphs_and_entities():
    assert html_to_text("<p>A &amp; B</p><p>C</p>") == "A & B\n\nC"


def test_loads_products_policies_and_pages():
    pieces = load_from_shopify(FakeClient())
    assert {p.source for p in pieces} == {"product", "policy", "page"}
    assert "164W cm" in pieces[0].text and "Yes & free." in pieces[-1].text
