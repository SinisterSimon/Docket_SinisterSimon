# Inbox

**An AI support inbox for Shopify stores: replies grounded in the store's own data, measured by evals.**

Customers write "where's my order?" or "does this come in blue?". Inbox looks the answer up in the
store's products, policies and orders, drafts a reply with its sources, and a person approves it.
A fixed set of test questions measures how often each model answers correctly, and how often it
invents facts.

Status: **Phase 0** (base app). See the roadmap below.

## Roadmap

| Phase | What | Status |
|---|---|---|
| 0 | Base app, shared LLM layer from Thread, CI | ✅ |
| 1 | Knowledge base: products + policies, embeddings, search (RAG) | next |
| 2 | Tools: order status, stock, product lookup (read-only Shopify) | |
| 3 | Triage: question / order issue / complaint / spam, hand-off rules | |
| 4 | Evals: ~50 questions with known answers; accuracy, invented facts, tone, hand-off | |
| 5 | Inbox UI: drafts with sources, approve / edit | |
| 6 | Real store in shadow mode | |
| 7 | Findings and write-up | |

## Run locally

```
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```
