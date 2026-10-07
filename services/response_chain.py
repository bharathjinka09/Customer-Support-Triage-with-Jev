"""Optional LangChain + Groq generation layer.

Jev makes the structured decision. The LLM is only used to draft natural
language after the decision is made.
"""
from __future__ import annotations

import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from services.jev_service import JevDecision


PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a concise SaaS customer-support assistant. Draft a helpful reply. "
            "Do not promise refunds, credits, account changes, or fixes that have not been confirmed. "
            "Keep the response under 120 words. If the case is routed to a human specialist, "
            "say that it is being escalated for review.",
        ),
        (
            "human",
            "Customer ticket:\n{ticket}\n\n"
            "Jev triage decision:\n"
            "- Department: {department}\n"
            "- Department confidence: {department_confidence:.2f}\n"
            "- Urgency score: {urgency_score:.2f} on a 0-3 rubric\n"
            "- Refund-related probability: {refund_probability:.2f}\n"
            "- Human-review probability: {human_review_probability:.2f}\n"
            "- Final route: {route}\n\n"
            "Write the suggested customer response.",
        ),
    ]
)


def draft_reply(ticket: str, decision: JevDecision, route: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key":
        return (
            "Jev analysis completed. Optional LangChain reply generation is disabled "
            "because GROQ_API_KEY is not configured."
        )

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    llm = ChatGroq(
        api_key=api_key,
        model=model,
        temperature=0.2,
        max_retries=2,
    )
    chain = PROMPT | llm | StrOutputParser()

    return chain.invoke(
        {
            "ticket": ticket,
            "department": decision.department,
            "department_confidence": decision.department_confidence,
            "urgency_score": decision.urgency_score,
            "refund_probability": decision.refund_probability,
            "human_review_probability": decision.human_review_probability,
            "route": route,
        }
    )
