"""Guardrail layer: every purchase must pass through check_policy() before a PayPal order exists."""
from dataclasses import dataclass, field, asdict

ALL_CATEGORIES = ["food", "home", "tech", "books", "fashion", "toys", "fitness", "gifts"]


@dataclass
class Rules:
    monthly_budget: float = 200.0
    max_per_purchase: float = 75.0
    approval_threshold: float = 25.0  # at or below -> one-click pay; above -> explicit approval
    allowed_categories: list = field(default_factory=lambda: list(ALL_CATEGORIES))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        base = cls()
        return cls(
            monthly_budget=float(d.get("monthly_budget", base.monthly_budget)),
            max_per_purchase=float(d.get("max_per_purchase", base.max_per_purchase)),
            approval_threshold=float(d.get("approval_threshold", base.approval_threshold)),
            allowed_categories=list(d.get("allowed_categories", base.allowed_categories)),
        )


def check_policy(amount: float, category: str, rules: Rules, spent_this_month: float) -> dict:
    """Return {"decision": "allow" | "needs_approval" | "block", "reason": str}."""
    amount = round(float(amount), 2)
    if amount <= 0:
        return {"decision": "block", "reason": "Invalid amount"}
    if category not in rules.allowed_categories:
        return {"decision": "block", "reason": f"Category '{category}' is not allowed"}
    if amount > rules.max_per_purchase:
        return {"decision": "block",
                "reason": f"${amount:.2f} is over your per-purchase limit of ${rules.max_per_purchase:.2f}"}
    if spent_this_month + amount > rules.monthly_budget:
        left = max(rules.monthly_budget - spent_this_month, 0)
        return {"decision": "block",
                "reason": f"Would exceed monthly budget (${left:.2f} left of ${rules.monthly_budget:.2f})"}
    if amount > rules.approval_threshold:
        return {"decision": "needs_approval",
                "reason": f"${amount:.2f} is above the ${rules.approval_threshold:.2f} auto-approve threshold"}
    return {"decision": "allow", "reason": "Within all rules"}
