"""Shopping agent. It can SEARCH and RECOMMEND only - it has no tool that can spend money."""
import json, os, re
from . import catalog

MODEL = os.environ.get("CARTPILOT_MODEL", "claude-sonnet-5-5")

SYSTEM = """You are CartPilot, a careful shopping agent. Use search_products to find items, then call
recommend_products with your top 1-3 picks and a one-sentence reason for each. Respect the user's
budget and the owner's spending rules shown below. You cannot buy anything: the owner approves and pays
through PayPal themselves. Keep replies short and friendly.
Owner's rules: {rules}"""

TOOLS = [
    {"name": "search_products", "description": "Search the product catalog.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "max_price": {"type": "number"}}, "required": ["query"]}},
    {"name": "recommend_products", "description": "Present final picks to the user.",
     "input_schema": {"type": "object", "properties": {
         "message": {"type": "string", "description": "Short message to the user"},
         "picks": {"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["id", "reason"]}}},
         "required": ["message", "picks"]}},
]


def _fallback(message):
    """No-LLM mode so the app (and tests) work without an API key."""
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:usd|dollars)|under\s+(\d+(?:\.\d+)?)", message.lower())
    max_price = float(next(g for g in m.groups() if g)) if m else None
    found = catalog.search(message, max_price, limit=3)
    if not found:
        return {"reply": "I couldn't find a match. Try describing the item or raising the budget.", "products": []}
    picks = [{**p, "reason": "Matches your request" + (f" and fits under ${max_price:.0f}" if max_price else "")}
             for p in found]
    return {"reply": f"Here are {len(picks)} options I found:", "products": picks}


def run_agent(message, rules):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(message)
    try:
        import anthropic
        client = anthropic.Anthropic()
        msgs = [{"role": "user", "content": message}]
        system = SYSTEM.format(rules=json.dumps(rules.to_dict()))
        seen = {}
        for _ in range(5):
            resp = client.messages.create(model=MODEL, max_tokens=1000, system=system,
                                          tools=TOOLS, messages=msgs)
            msgs.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                if block.name == "search_products":
                    found = catalog.search(block.input["query"], block.input.get("max_price"), limit=6)
                    for p in found:
                        seen[p["id"]] = p
                    out = [{k: p[k] for k in ("id", "title", "price", "category", "description")} for p in found]
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)})
                elif block.name == "recommend_products":
                    picks = []
                    for pk in block.input.get("picks", []):
                        p = seen.get(pk["id"]) or catalog.get(pk["id"])
                        if p:
                            picks.append({**p, "reason": pk["reason"]})
                    return {"reply": block.input.get("message", "Here are my picks:"), "products": picks}
            if not results:
                text = "".join(b.text for b in resp.content if b.type == "text")
                return {"reply": text or "How can I help?", "products": []}
            msgs.append({"role": "user", "content": results})
        return _fallback(message)
    except Exception as e:  # never let the LLM break the demo
        out = _fallback(message)
        out["reply"] += f"  (LLM unavailable: {type(e).__name__}; used basic search)"
        return out
