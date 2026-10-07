from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import os

ssl_cert_file = os.getenv("SSL_CERT_FILE")

if ssl_cert_file and not Path(ssl_cert_file).exists():
    print(f"Removing invalid SSL_CERT_FILE: {ssl_cert_file}")
    os.environ.pop("SSL_CERT_FILE", None)


# Always resolve paths relative to THIS file, not the terminal working directory.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from services.jev_service import analyze_ticket
from services.response_chain import draft_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jev-support-triage")

app = FastAPI(title="Jev Smart Support Triage", version="1.1.0")

# Absolute paths prevent Windows FileNotFoundError / [Errno 2] issues.
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class TicketRequest(BaseModel):
    ticket: str = Field(min_length=5, max_length=8000)


def choose_route(
    department: str,
    dept_conf: float,
    urgency: float,
    human_prob: float,
) -> tuple[str, bool, str]:
    """Deterministic business rules belong in normal code."""
    needs_human = human_prob >= 0.65 or dept_conf < 0.60 or urgency >= 2.5

    if needs_human:
        return (
            f"{department.title()} → Human specialist",
            True,
            "Escalated by confidence/risk threshold",
        )

    return (
        f"{department.title()} queue",
        False,
        "Safe for normal queue routing",
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # New Starlette/FastAPI TemplateResponse signature.
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.post("/api/analyze")
def analyze(payload: TicketRequest):
    ticket = payload.ticket.strip()

    try:
        decision = analyze_ticket(ticket)
    except Exception as exc:
        logger.exception("Jev analysis failed")
        raise HTTPException(
            status_code=502,
            detail=f"Jev API error: {exc}",
        ) from exc

    route, needs_human, rule_reason = choose_route(
        decision.department,
        decision.department_confidence,
        decision.urgency_score,
        decision.human_review_probability,
    )

    # The generative reply is intentionally non-blocking. If Groq fails,
    # Jev results still render so the main demo remains usable.
    try:
        reply = draft_reply(ticket, decision, route)
    except Exception as exc:
        logger.exception("Reply generation failed")
        reply = (
            "Jev analysis completed successfully, but the optional LangChain/Groq "
            f"reply generation failed: {exc}"
        )

    return {
        "ticket": ticket,
        "jev": {
            "model": decision.model,
            "department": decision.department,
            "department_confidence": round(decision.department_confidence, 4),
            "urgency_score": round(decision.urgency_score, 4),
            "urgency_confidence": round(decision.urgency_confidence, 4),
            "refund_probability": round(decision.refund_probability, 4),
            "human_review_probability": round(decision.human_review_probability, 4),
        },
        "automation": {
            "route": route,
            "needs_human": needs_human,
            "reason": rule_reason,
        },
        "suggested_reply": reply,
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)