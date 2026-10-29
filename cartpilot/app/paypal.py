"""PayPal Orders API v2 (sandbox by default). Falls back to a local mock when no credentials are set."""
import base64, json, os, time, urllib.request, urllib.error

BASE = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
_token = {"value": None, "exp": 0}


def client_id():
    return os.environ.get("PAYPAL_CLIENT_ID", "")


def is_mock():
    return os.environ.get("MOCK_PAYPAL") == "1" or not (client_id() and os.environ.get("PAYPAL_CLIENT_SECRET"))


def _request(method, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"PayPal {e.code}: {e.read().decode()[:400]}")


def _access_token():
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    auth = base64.b64encode(f"{client_id()}:{os.environ.get('PAYPAL_CLIENT_SECRET','')}".encode()).decode()
    res = _request("POST", "/v1/oauth2/token", raw=b"grant_type=client_credentials",
                   headers={"Authorization": f"Basic {auth}",
                            "Content-Type": "application/x-www-form-urlencoded"})
    _token.update(value=res["access_token"], exp=time.time() + res.get("expires_in", 300))
    return _token["value"]


def _auth_headers():
    return {"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"}


def create_order(amount, description, reference_id):
    if is_mock():
        return {"id": f"MOCK-ORDER-{reference_id}", "status": "CREATED"}
    body = {"intent": "CAPTURE",
            "purchase_units": [{"reference_id": str(reference_id), "description": description[:120],
                                "amount": {"currency_code": "USD", "value": f"{amount:.2f}"}}]}
    return _request("POST", "/v2/checkout/orders", body=body, headers=_auth_headers())


def capture_order(order_id):
    if is_mock():
        return {"id": order_id, "status": "COMPLETED"}
    return _request("POST", f"/v2/checkout/orders/{order_id}/capture", body={}, headers=_auth_headers())
