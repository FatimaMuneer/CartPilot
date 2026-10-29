import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, catalog, db, paypal
from .policy import Rules, check_policy, ALL_CATEGORIES

app = FastAPI(title="CartPilot")
db.init()
STATIC = os.path.join(os.path.dirname(__file__), "..", "static")


class Msg(BaseModel):
    message: str


class ProductReq(BaseModel):
    product_id: str


class OrderReq(BaseModel):
    request_id: int


class CaptureReq(BaseModel):
    request_id: int
    order_id: str


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/config")
def config():
    return {"paypal_client_id": paypal.client_id(), "mock_paypal": paypal.is_mock(),
            "categories": ALL_CATEGORIES, "llm": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.get("/api/rules")
def get_rules():
    return db.get_rules().to_dict()


@app.put("/api/rules")
def put_rules(body: dict):
    rules = Rules.from_dict(body)
    if rules.monthly_budget < 0 or rules.max_per_purchase < 0 or rules.approval_threshold < 0:
        raise HTTPException(400, "Values must be positive")
    db.set_rules(rules)
    return rules.to_dict()


@app.get("/api/dashboard")
def dashboard():
    rules = db.get_rules()
    return {"rules": rules.to_dict(), "spent": db.spent_this_month(),
            "requests": db.list_requests(), "audit": db.audit_log()}


@app.post("/api/agent")
def ask_agent(body: Msg):
    db.log("user_message", {"text": body.message[:300]})
    result = agent.run_agent(body.message, db.get_rules())
    db.log("agent_recommended", {"products": [p["id"] for p in result["products"]]})
    return result


@app.post("/api/purchase-request")
def purchase_request(body: ProductReq):
    product = catalog.get(body.product_id)
    if not product:
        raise HTTPException(404, "Unknown product")
    verdict = check_policy(product["price"], product["category"], db.get_rules(), db.spent_this_month())
    return db.add_request(product, verdict["decision"], verdict["reason"])


@app.post("/api/requests/{rid}/approve")
def approve(rid: int):
    req = db.get_request(rid)
    if not req or req["status"] != "awaiting_approval":
        raise HTTPException(400, "Request is not awaiting approval")
    db.set_status(rid, "approved")
    return db.get_request(rid)


@app.post("/api/requests/{rid}/reject")
def reject(rid: int):
    req = db.get_request(rid)
    if not req or req["status"] not in ("awaiting_approval", "approved"):
        raise HTTPException(400, "Request cannot be rejected")
    db.set_status(rid, "rejected")
    return db.get_request(rid)


@app.post("/api/paypal/create-order")
def create_order(body: OrderReq):
    req = db.get_request(body.request_id)
    if not req or req["status"] != "approved":
        raise HTTPException(400, "Purchase is not approved")
    # Re-check the guardrails server-side: amount comes from our DB, never from the browser.
    verdict = check_policy(req["amount"], req["category"], db.get_rules(), db.spent_this_month())
    if verdict["decision"] == "block":
        db.set_status(req["id"], "blocked", reason=verdict["reason"])
        raise HTTPException(403, verdict["reason"])
    try:
        order = paypal.create_order(req["amount"], req["title"], req["id"])
    except RuntimeError as e:
        db.log("paypal_error", {"request_id": req["id"], "error": str(e)})
        raise HTTPException(502, str(e))
    db.set_status(req["id"], "approved", paypal_order_id=order["id"])
    return {"id": order["id"]}


@app.post("/api/paypal/capture-order")
def capture_order(body: CaptureReq):
    req = db.get_request(body.request_id)
    if not req or req["paypal_order_id"] != body.order_id:
        raise HTTPException(400, "Order does not match request")
    try:
        result = paypal.capture_order(body.order_id)
    except RuntimeError as e:
        db.log("paypal_error", {"request_id": req["id"], "error": str(e)})
        raise HTTPException(502, str(e))
    if result.get("status") == "COMPLETED":
        db.set_status(req["id"], "paid", paid_at=db.now())
    return {"status": result.get("status"), "request": db.get_request(req["id"])}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
