# Docket

**An AI support desk for Shopify stores: replies grounded in the store's own data, measured by evals.**

Customers write "where's my order?" or "does this come in blue?". Docket looks the answer up in the
store's products, policies and orders, drafts a reply with its sources, and a person approves it.
A fixed set of test questions measures how often each model answers correctly, and how often it
invents facts.

Status: **Phase 2** (agent with tools). See the roadmap below.

## Roadmap

| Phase | What | Status |
|---|---|---|
| 0 | Base app, shared LLM layer from Thread, CI | ✅ |
| 1 | Knowledge base: products + policies, embeddings, search (RAG) | ✅ |
| 2 | Tools: order status, stock, product lookup (read-only Shopify) | ✅ |
| 3 | Triage: question / order issue / complaint / spam, hand-off rules | next |
| 4 | Evals: ~50 questions with known answers; accuracy, invented facts, tone, hand-off | |
| 5 | Docket UI: drafts with sources, approve / edit | |
| 6 | Real store in shadow mode | |
| 7 | Findings and write-up | |

## Design decisions so far

- **Vectors in a JSON column, searched in Python.** A store has hundreds of chunks, not millions;
  a full scan takes milliseconds and runs on SQLite and Postgres alike. pgvector is the upgrade path.
- **One chunk per policy section.** Small, single-topic chunks make retrieval precise and let a reply
  cite exactly which section it used.
- **Offline embedder for tests.** Word hashing is free and deterministic. It matches words, not meaning,
  so it tests the plumbing; real quality is measured with OpenAI embeddings in the evals (phase 4).
- **Embed model stored per chunk.** Vectors from different models can't be compared, so search ignores
  chunks made by another model instead of returning nonsense.

- **Tool calls as one JSON object per turn.** The same loop works with Claude, GPT and Gemini through
  Thread's provider-neutral LLM layer, and offline a rule-based planner scripts the same turns so the
  loop is tested for free. Native function calling per provider is the upgrade path.
- **Order lookups check the sender's email.** A stranger who guesses an order number gets "no order
  found", not someone else's address and items.
- **Stock says "in stock" or "sold out", never unit counts.** Exact inventory is business data a
  customer doesn't need.
- **Every draft keeps its sources and tool calls.** A reviewer sees where each fact came from, and the
  evals can check that every fact in a reply was actually looked up.

## Run locally

```
pip install -r requirements.txt
uvicorn app.main:app --reload   # then open /knowledge and click Rebuild
pytest
```
