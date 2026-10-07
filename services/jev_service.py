"""Official TypeSafe/Jev API integration.

This implementation intentionally uses the documented HTTPS endpoint directly
instead of relying on SDK-specific internals. That makes the demo small,
transparent, and less sensitive to SDK version changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class JevDecision:
    department: str
    department_confidence: float
    urgency_score: float
    urgency_confidence: float
    refund_probability: float
    human_review_probability: float
    model: str | None = None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _answer(answers: dict[str, Any], key: str) -> dict[str, Any]:
    value = answers.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"Jev response is missing the '{key}' answer.")
    return value


def analyze_ticket(ticket: str) -> JevDecision:
    api_key = os.getenv("TYPESAFE_API_KEY", "").strip()
    if not api_key or api_key == "your_typesafe_api_key":
        raise RuntimeError(
            "TYPESAFE_API_KEY is not configured. Create a .env file and add your TypeSafe API key."
        )

    model = os.getenv("TYPESAFE_MODEL", "jev-latest").strip() or "jev-latest"
    api_url = os.getenv(
        "TYPESAFE_API_URL",
        "https://api.typesafe.ai/v1/systemone",
    ).strip()

    # Keep the state readable for a beginner-friendly demo.
    state = (
        "Task context: Customer support triage for a SaaS product.\n"
        f"Customer ticket: {ticket}"
    )

    payload = {
        "state": state,
        "model": model,
        "questions": {
            "department": {
                "type": "choice",
                "instructions": "Which support team should own this ticket?",
                "criteria": {
                    "billing": "Charges, invoices, payments, refunds, subscriptions, or pricing already paid",
                    "technical": "Bugs, errors, integrations, login failures, or product functionality problems",
                    "account": "Profile, access, permissions, plan/account settings, or identity-related issues",
                    "general": "Questions that do not clearly fit billing, technical, or account",
                },
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this customer request?",
                "criteria": [
                    "Low: informational or no meaningful time pressure",
                    "Medium: customer is blocked or inconvenienced but can wait",
                    "High: business impact, repeated failure, or explicit need for fast help",
                    "Critical: severe ongoing financial/security impact or complete business stoppage",
                ],
            },
            "refund_related": {
                "type": "noul",
                "instructions": "The customer is asking for, expecting, or clearly discussing a refund or reversal of money.",
            },
            "human_review": {
                "type": "noul",
                "instructions": (
                    "This ticket should be reviewed by a human before any automated action "
                    "because it is ambiguous, sensitive, high impact, or could create financial/account risk."
                ),
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    timeout_seconds = _as_float(os.getenv("TYPESAFE_TIMEOUT", "30"), 30.0)

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(api_url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to TypeSafe API ({type(exc).__name__}: {exc})."
        ) from exc

    if response.status_code >= 400:
        try:
            error_body = response.json()
        except Exception:
            error_body = response.text
        raise RuntimeError(
            f"TypeSafe returned HTTP {response.status_code}: {error_body}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("TypeSafe returned a non-JSON response.") from exc

    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise RuntimeError(f"Unexpected TypeSafe response: {data}")

    department_answer = _answer(answers, "department")
    urgency_answer = _answer(answers, "urgency")
    refund_answer = _answer(answers, "refund_related")
    human_answer = _answer(answers, "human_review")

    department = str(department_answer.get("choice", "general"))

    return JevDecision(
        department=department,
        department_confidence=_as_float(department_answer.get("confidence")),
        urgency_score=_as_float(urgency_answer.get("score")),
        urgency_confidence=_as_float(urgency_answer.get("confidence")),
        refund_probability=_as_float(refund_answer.get("noul")),
        human_review_probability=_as_float(human_answer.get("noul")),
        model=str(data.get("model")) if data.get("model") is not None else model,
    )
