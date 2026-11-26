# Docket: notes for AI coding assistants

An AI support desk for Shopify stores. Sister project of Thread (SinisterSimon/Thread_SinisterSimon).

## Commands
- Run: `uvicorn app.main:app --reload` (http://localhost:8000)
- Test: `pytest` (offline, no API key needed)
- Lint: `ruff check .`

## Rules
- Never import a provider SDK outside `app/llm/`. Call `traced(...)`.
- Replies may only state facts found by retrieval or a tool call; anything else is an invented fact and the evals count it.
- Nothing is sent to a customer without a human approving it.
- Offline mode stays free and deterministic; tests never call a real API.
- Money is integer cents. Branch per change, PR into `main`.
