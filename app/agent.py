"""The support agent: look things up with tools, then draft a reply a human approves.

Tool calling uses a small JSON protocol that works the same with every provider:
each turn the model answers with exactly one JSON object, either
  {"tool": "<name>", "args": {...}}   to look something up, or
  {"reply": "<text>", "handoff": false} to finish.
Thread's LLM layer stays provider-neutral this way. Native function calling is the upgrade path.

Offline, a deterministic planner scripts the same JSON turns, so the loop itself is tested for free.
"""
import json
import re
from dataclasses import dataclass, field

from app.llm import LLM, Message, traced
from app.llm.client import LLMError, OfflineLLM
from app.tools import ORDER_NUMBER, TOOL_SPEC, ToolBox

MAX_STEPS = 5
DEFAULT_MODEL = "claude-sonnet-5-5"

RULES = """You answer customer emails for STORE_NAME, a snowboard shop.

TOOL_SPEC

Rules:
- Only state facts that a tool returned. If the tools don't have the answer, say you'll check and hand off.
- Look up before answering: policies with search_knowledge, orders with order_status, sizes with check_stock.
- Hand off to a person (handoff true) for complaints, damaged goods, legal threats, refunds outside policy,
  or anything you can't answer from the tools.
- Short, warm, plain. Use the customer's name if known. No discounts, no promises the tools don't support.

Answer with exactly one JSON object and nothing else:
{"tool": "<name>", "args": {...}}  or  {"reply": "<email text>", "handoff": false}"""

HANDOFF_WORDS = re.compile(r"\b(broken|damaged|cracked|refund|lawyer|complain|angry|terrible|worst|scam)\b", re.I)
STOCK_WORDS = re.compile(r"\b(stock|available|sold out|have .* in|size)\b", re.I)


@dataclass
class Step:
    tool: str
    args: dict
    result: str


@dataclass
class AgentResult:
    reply: str
    handoff: bool
    steps: list[Step] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def parse_action(text: str) -> dict:
    """The JSON object in a model reply, tolerating code fences and text around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object")
    action = json.loads(text[start : end + 1])
    if not isinstance(action, dict) or not ({"tool", "reply"} & action.keys()):
        raise ValueError("JSON has neither 'tool' nor 'reply'")
    return action


def offline_plan(body: str, steps: list[Step]) -> dict:
    """What a sensible agent would do next, written as rules. Used only offline."""
    done = {s.tool for s in steps}
    if HANDOFF_WORDS.search(body):
        return {"reply": "Thanks for letting us know. A member of our team will reply personally today.",
                "handoff": True}
    if (m := ORDER_NUMBER.search(body)) and "order_status" not in done:
        return {"tool": "order_status", "args": {"order_number": m.group(1)}}
    if STOCK_WORDS.search(body) and "check_stock" not in done:
        return {"tool": "check_stock", "args": {"product": _product_in(body)}}
    if "search_knowledge" not in done:
        return {"tool": "search_knowledge", "args": {"query": body}}
    facts = " ".join(s.result.split("\n\n")[0] for s in steps)
    return {"reply": f"Hi! Here's what I found: {facts[:600]}", "handoff": False}


def _product_in(body: str) -> str:
    for name in ("oxygen", "multi-location", "compare at price"):
        if name in body.lower():
            return name
    return body[:60]


def answer(llm: LLM, tools: ToolBox, subject: str, body: str, *, store_name: str = "Thread Snow Co.",
           model: str = DEFAULT_MODEL) -> AgentResult:
    system = RULES.replace("STORE_NAME", store_name).replace("TOOL_SPEC", TOOL_SPEC)
    history = [Message(role="user", text=f"From: {tools.sender}\nSubject: {subject}\n\n{body}")]
    result = AgentResult(reply="", handoff=True, model=model)
    for _ in range(MAX_STEPS):
        sys = system
        if isinstance(llm, OfflineLLM):
            sys += f"\n{OfflineLLM.MARKER}{json.dumps(offline_plan(body, result.steps))}"
        reply = traced("docket:agent", llm, system=sys, messages=history, model=model)
        result.input_tokens += reply.input_tokens
        result.output_tokens += reply.output_tokens
        result.model = reply.model
        try:
            action = parse_action(reply.text)
        except (ValueError, json.JSONDecodeError):
            history += [Message(role="assistant", text=reply.text),
                        Message(role="user", text="Answer with one JSON object only, as instructed.")]
            continue
        if "reply" in action:
            result.reply = str(action["reply"]).strip()
            result.handoff = bool(action.get("handoff", False))
            return result
        out = tools.call(str(action["tool"]), dict(action.get("args") or {}))
        result.steps.append(Step(str(action["tool"]), dict(action.get("args") or {}), out.text))
        result.sources += [s for s in out.sources if s not in result.sources]
        history += [Message(role="assistant", text=reply.text),
                    Message(role="user", text=f"Tool result ({action['tool']}):\n{out.text}")]
    result.reply = result.reply or "(No reply: the agent ran out of steps. A person should answer.)"
    return result


__all__ = ["AgentResult", "LLMError", "Step", "answer", "parse_action"]
