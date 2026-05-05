import os

import pytest

from onboarding.content import generate_content_bundle


@pytest.mark.asyncio
async def test_stub_bundle_when_no_api_key():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    bundle = await generate_content_bundle(
        partner_name="Acme",
        primary_contact_name="Pat",
        tier="gold",
        services=["managed-soc"],
    )
    assert len(bundle.email_sequence) == 5
    assert all({"day_offset", "subject", "body", "purpose"} <= e.keys() for e in bundle.email_sequence)
    assert "Kickoff Call" in bundle.kickoff_agenda
    assert 8 <= len(bundle.readiness_checklist) <= 12
