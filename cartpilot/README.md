# 🛒 CartPilot – AI shopping agent with spending guardrails

Built for the PayPal AI Hackathon. An AI agent finds and compares products, but it can **never spend money itself**.
Every purchase goes through a policy engine (budget, per-purchase cap, allowed categories, approval threshold),
then the human approves and pays through **PayPal**. Every decision is written to an audit trail.

## How it works
```
user ─► agent (search_products, recommend_products only)
              │ picks
user clicks Buy ─► POST /api/purchase-request ─► check_policy() ─► allow | needs_approval | block
                                                                         │
            approve (if needed) ─► POST /api/paypal/create-order (re-checks policy server-side)
                                 ─► PayPal buttons ─► POST /api/paypal/capture-order ─► audit log + budget updated
```
Key safety property: the order amount is read from the server database, never from the browser, and the
policy is checked again right before the PayPal order is created.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill in keys (see below)
export $(grep -v '^#' .env | xargs)                    # Windows PowerShell: set each variable with $env:NAME="value"
uvicorn app.main:app --reload
# open http://localhost:8000
```
No keys yet? Run `MOCK_PAYPAL=1 uvicorn app.main:app --reload` for a fully local demo with simulated payments
and a basic keyword agent.

Run the tests: `python -m unittest discover -s tests -v`

## Configuration
| Variable | Purpose |
|---|---|
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | PayPal **Sandbox** app credentials |
| `ANTHROPIC_API_KEY` | Optional. Enables the LLM agent (tool calling). Without it a basic agent is used |
| `CARTPILOT_MODEL` | Optional. LLM model name (default `claude-sonnet-5-5`) |
| `CHANNEL3_API_KEY` | Optional. Live product data, wire up `search_channel3()` in `app/catalog.py` |
| `MOCK_PAYPAL=1` | Force simulated payments |

## Deploy on Render
1. Push this repo to GitHub.
2. Render → New → Blueprint → select the repo (it reads `render.yaml`).
3. Add the environment variables above in the Render dashboard.
4. Your live URL will look like `https://cartpilot.onrender.com`.

## Notes
- Demo app: single user, no login, SQLite storage (resets on free-tier redeploys).
- Uses PayPal **Sandbox** only. No real money moves.
