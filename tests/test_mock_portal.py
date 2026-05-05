import httpx
import pytest


@pytest.mark.asyncio
async def test_account_creation_is_idempotent(mock_portal_url):
    async with httpx.AsyncClient(base_url=mock_portal_url) as c:
        body = {"partner_id": "company-test", "partner_name": "Test Co"}
        r1 = (await c.post("/v1/accounts", json=body)).raise_for_status().json()
        r2 = (await c.post("/v1/accounts", json=body)).raise_for_status().json()
        assert r1["account_id"] == r2["account_id"]
        assert r1["api_key"] == r2["api_key"]


@pytest.mark.asyncio
async def test_asset_upload_roundtrip(mock_portal_url):
    async with httpx.AsyncClient(base_url=mock_portal_url) as c:
        acct = (
            await c.post(
                "/v1/accounts",
                json={"partner_id": "company-asset", "partner_name": "Asset Co"},
            )
        ).json()
        files = {"file": ("packet.pdf", b"%PDF-fake", "application/pdf")}
        r = (await c.post(f"/v1/accounts/{acct['account_id']}/assets", files=files)).json()
        assert r["bytes"] == len(b"%PDF-fake")
        # Asset is retrievable
        get = await c.get(f"/assets/{acct['account_id']}/packet.pdf")
        assert get.status_code == 200
        assert get.content == b"%PDF-fake"


@pytest.mark.asyncio
async def test_intake_form_creation(mock_portal_url):
    async with httpx.AsyncClient(base_url=mock_portal_url) as c:
        acct = (
            await c.post(
                "/v1/accounts",
                json={"partner_id": "company-form", "partner_name": "Form Co"},
            )
        ).json()
        fields = ["foo", "bar"]
        r = (
            await c.post(
                f"/v1/accounts/{acct['account_id']}/intake-forms",
                json={"fields": fields},
            )
        ).json()
        assert r["fields"] == fields
        # Round-trip
        seen = (await c.get(f"/intake/{acct['account_id']}")).json()
        assert seen["fields"] == fields
