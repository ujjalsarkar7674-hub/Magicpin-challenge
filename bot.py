"""
magicpin AI Challenge — Vera Bot Implementation
================================================
Production-grade FastAPI server + standalone compose interface.
Exposes the 5 required endpoints under /v1/* with sub-millisecond response latency,
deterministic 4-context composition, and robust multi-turn handling.
"""

from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field
import uvicorn

from composer import compose as core_compose
from conversation_handlers import respond as core_respond

app = FastAPI(title="Vera Merchant AI Assistant", version="1.0.0")
START_TIME = time.time()

# In-Memory Thread-Safe State Stores
contexts: Dict[tuple[str, str], Dict[str, Any]] = {}  # (scope, context_id) -> {version, payload}
conversations: Dict[str, List[Dict[str, Any]]] = {}     # conversation_id -> [turns]


# ---------------------------------------------------------------------------
# Canonical Submission Function (challenge-brief.md §7.1)
# ---------------------------------------------------------------------------
def compose(
    category: dict,
    merchant: dict,
    trigger: dict,
    customer: Optional[dict] = None
) -> dict:
    """
    Inputs are dicts matching CategoryContext, MerchantContext, TriggerContext, CustomerContext.
    Returns: {body, cta, send_as, suppression_key, rationale}
    """
    return core_compose(category, merchant, trigger, customer)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class ContextPushRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1


# ---------------------------------------------------------------------------
# Endpoints (challenge-testing-brief.md §2)
# ---------------------------------------------------------------------------
@app.get("/v1/healthz")
async def healthz():
    """Liveness probe reporting uptime and context inventory."""
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        if scope in counts:
            counts[scope] += 1
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts_loaded": counts
    }


@app.get("/v1/metadata")
async def metadata():
    """Bot metadata, identity, and architectural specifications."""
    return {
        "team_name": "Vera AI Team",
        "team_members": ["Vera Core"],
        "model": "deterministic-4context-composer",
        "approach": (
            "4-context engagement framework with trigger-kind dispatching, "
            "verifiable fact anchoring, auto-reply classification, and intent-first routing"
        ),
        "contact_email": "vera-team@magicpin.in",
        "version": "1.0.0",
        "submitted_at": "2026-04-26T08:00:00Z"
    }


@app.post("/v1/context")
async def push_context(body: ContextPushRequest, response: Response):
    """
    Idempotent, version-aware context push across category, merchant, customer, trigger.
    Replaces lower versions atomically; rejects stale versions with 409.
    """
    key = (body.scope, body.context_id)
    cur = contexts.get(key)

    # Strictly lower version is rejected as stale
    if cur and cur.get("version", 0) > body.version:
        response.status_code = status.HTTP_409_CONFLICT
        return {
            "accepted": False,
            "reason": "stale_version",
            "current_version": cur.get("version")
        }

    # Same version is an idempotent no-op acceptance
    if cur and cur.get("version", 0) == body.version:
        return {
            "accepted": True,
            "ack_id": f"ack_{body.context_id}_v{body.version}",
            "stored_at": cur.get("delivered_at") or datetime.now(timezone.utc).isoformat()
        }

    contexts[key] = {
        "version": body.version,
        "payload": body.payload,
        "delivered_at": body.delivered_at or datetime.now(timezone.utc).isoformat()
    }

    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat()
    }


@app.post("/v1/tick")
async def tick(body: TickRequest):
    """
    Periodic wake-up endpoint. Inspects available triggers and generates proactive messages.
    """
    actions = []
    
    for trg_id in body.available_triggers:
        trg_ctx = contexts.get(("trigger", trg_id), {}).get("payload")
        if not trg_ctx:
            continue
            
        merchant_id = trg_ctx.get("merchant_id") or trg_ctx.get("payload", {}).get("merchant_id")
        mer_ctx = contexts.get(("merchant", merchant_id), {}).get("payload") if merchant_id else None
        
        customer_id = trg_ctx.get("customer_id")
        cust_ctx = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
        
        cat_slug = None
        if mer_ctx:
            cat_slug = mer_ctx.get("category_slug")
        elif trg_ctx.get("payload", {}).get("category"):
            cat_slug = trg_ctx["payload"]["category"]
            
        cat_ctx = contexts.get(("category", cat_slug), {}).get("payload") if cat_slug else None
        
        if not (mer_ctx and cat_ctx):
            continue
            
        comp = compose(cat_ctx, mer_ctx, trg_ctx, cust_ctx)
        
        actions.append({
            "conversation_id": f"conv_{merchant_id}_{trg_id}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": comp["send_as"],
            "trigger_id": trg_id,
            "template_name": f"vera_{trg_ctx.get('kind', 'generic')}_v1",
            "template_params": [
                mer_ctx.get("identity", {}).get("name", ""),
                trg_ctx.get("kind", ""),
                comp["cta"]
            ],
            "body": comp["body"],
            "cta": comp["cta"],
            "suppression_key": comp["suppression_key"],
            "rationale": comp["rationale"]
        })
        
    return {"actions": actions}


@app.post("/v1/reply")
async def reply(body: ReplyRequest):
    """
    Receives merchant/customer replies and executes intelligent multi-turn routing:
    auto-reply termination, intent transitions, back-off waits, and active responses.
    """
    conv_history = conversations.setdefault(body.conversation_id, [])
    conv_history.append({
        "from": body.from_role,
        "msg": body.message,
        "ts": body.received_at or datetime.now(timezone.utc).isoformat()
    })
    
    resp = core_respond(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
        history=conv_history
    )
    
    if resp.get("action") == "send":
        conv_history.append({
            "from": "vera",
            "msg": resp.get("body", ""),
            "ts": datetime.now(timezone.utc).isoformat()
        })
        
    return resp


# ---------------------------------------------------------------------------
# Server Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("bot:app", host="0.0.0.0", port=port, log_level="info")
