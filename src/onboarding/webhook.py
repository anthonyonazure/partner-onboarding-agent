"""FastAPI receiver for HubSpot deal-stage-changed webhooks.

Production: validate HubSpot's X-HubSpot-Signature-v3 header against your secret
before enqueueing. The portfolio version skips that for clarity.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from fastapi import BackgroundTasks, FastAPI, Request

from onboarding.graph import build_graph
from onboarding.state import OnboardingState

log = structlog.get_logger()
app = FastAPI(title="Partner Onboarding Webhook")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/hubspot/deal-stage-changed")
async def deal_stage_changed(req: Request, bg: BackgroundTasks) -> dict[str, Any]:
    payload = await req.json()
    # HubSpot batches events; in real usage iterate and filter
    deal_id = str(payload.get("objectId") or payload.get("deal_id") or "")
    new_stage = payload.get("propertyValue") or payload.get("dealstage")
    if not deal_id or new_stage != "closedwon":
        return {"ignored": True}

    run_id = uuid.uuid4().hex[:10]
    bg.add_task(_run_onboarding, deal_id, run_id)
    log.info("webhook.enqueued", deal_id=deal_id, run_id=run_id)
    return {"enqueued": True, "run_id": run_id, "deal_id": deal_id}


async def _run_onboarding(deal_id: str, run_id: str) -> None:
    initial: OnboardingState = {"deal_id": deal_id, "run_id": run_id, "events": [], "errors": []}
    graph = build_graph().compile()
    try:
        await graph.ainvoke(initial)
        log.info("onboarding.done", run_id=run_id, deal_id=deal_id)
    except Exception as e:
        log.exception("onboarding.failed", run_id=run_id, deal_id=deal_id, err=str(e))
