"""Mock of the internal portal API.

Exposes the same OpenAPI surface b2b_toolkit.adapters.portal.PortalClient expects.
Run: `mock-portal` or `python -m mock_portal.main`.
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

app = FastAPI(title="Internal Portal API (mock)", version="0.1.0")
_ASSETS_DIR = Path("out/mock_portal_assets")
_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

_ACCOUNTS: dict[str, dict] = {}
_ASSETS: dict[str, list[str]] = {}
_INTAKE_FORMS: dict[str, list[str]] = {}


class CreateAccountRequest(BaseModel):
    partner_id: str
    partner_name: str


class CreateAccountResponse(BaseModel):
    account_id: str
    partner_id: str
    api_key: str
    intake_form_url: str


class IntakeFormRequest(BaseModel):
    fields: list[str]


def _base(req: Request) -> str:
    return str(req.base_url).rstrip("/")


@app.post("/v1/accounts", response_model=CreateAccountResponse)
async def create_account(body: CreateAccountRequest, req: Request) -> CreateAccountResponse:
    base = _base(req)
    # Idempotency: same partner_id returns same account
    for acct in _ACCOUNTS.values():
        if acct["partner_id"] == body.partner_id:
            # Rebuild URL with current host (in case server moved)
            return CreateAccountResponse(
                **{**acct, "intake_form_url": f"{base}/intake/{acct['account_id']}"}
            )
    account_id = "acct_" + uuid.uuid4().hex[:10]
    record = {
        "account_id": account_id,
        "partner_id": body.partner_id,
        "api_key": "ptl_" + secrets.token_urlsafe(20),
        "intake_form_url": f"{base}/intake/{account_id}",
    }
    _ACCOUNTS[account_id] = record
    return CreateAccountResponse(**record)


@app.post("/v1/accounts/{account_id}/assets")
async def upload_asset(account_id: str, req: Request, file: UploadFile = File(...)) -> dict:
    if account_id not in _ACCOUNTS:
        raise HTTPException(404, "account not found")
    content = await file.read()
    safe_name = file.filename.replace("/", "_")
    target = _ASSETS_DIR / f"{account_id}_{safe_name}"
    target.write_bytes(content)
    _ASSETS.setdefault(account_id, []).append(safe_name)
    return {"url": f"{_base(req)}/assets/{account_id}/{safe_name}", "bytes": len(content)}


@app.post("/v1/accounts/{account_id}/intake-forms")
async def create_intake_form(account_id: str, body: IntakeFormRequest, req: Request) -> dict:
    if account_id not in _ACCOUNTS:
        raise HTTPException(404, "account not found")
    _INTAKE_FORMS[account_id] = body.fields
    return {"url": f"{_base(req)}/intake/{account_id}", "fields": body.fields}


@app.get("/v1/accounts/{account_id}/usage")
async def get_usage(account_id: str, days: int = 30) -> dict:
    if account_id not in _ACCOUNTS:
        raise HTTPException(404, "account not found")
    return {
        "account_id": account_id,
        "window_days": days,
        "logins": 42,
        "modules_active": ["soc-dashboard", "vuln-scanner", "incident-tracker"],
        "modules_unused": ["compliance-reports"],
        "last_login_days_ago": 2,
    }


@app.get("/intake/{account_id}")
async def show_intake(account_id: str) -> dict:
    return {"account_id": account_id, "fields": _INTAKE_FORMS.get(account_id, [])}


@app.get("/assets/{account_id}/{filename}")
async def get_asset(account_id: str, filename: str):
    from fastapi.responses import FileResponse

    path = _ASSETS_DIR / f"{account_id}_{filename}"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


def run() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    run()
