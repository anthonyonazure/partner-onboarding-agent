"""End-to-end test: run the full LangGraph against mocks + live mock portal."""

from __future__ import annotations

from collections import Counter

import pytest

from onboarding.graph import build_graph
from onboarding.state import OnboardingState


@pytest.mark.asyncio
async def test_full_onboarding_run(mock_portal_url, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    graph = build_graph().compile()
    initial: OnboardingState = {
        "deal_id": "deal-001",
        "run_id": "test-run",
        "events": [],
        "errors": [],
    }
    final = await graph.ainvoke(initial)

    # Partner profile resolved
    assert final["partner_name"] == "Acme Corp"
    assert final["tier"] == "gold"

    # All provisioning happened exactly once
    event_kinds = Counter(e["kind"] for e in final["events"])
    assert event_kinds["partner_profile_loaded"] == 1
    assert event_kinds["m365_provisioned"] == 1
    assert event_kinds["zendesk_provisioned"] == 1
    assert event_kinds["portal_provisioned"] == 1
    assert event_kinds["content_generated"] == 1
    assert event_kinds["pdf_packet_built"] == 1
    assert event_kinds["hubspot_note_posted"] == 1, "post-back must fire exactly once (was the bug)"

    # Resources captured in state
    assert final["mailbox_upn"].endswith("@mock.tenant")
    assert final["sharepoint_url"].startswith("https://mock.sharepoint.com/")
    assert isinstance(final["zendesk_org_id"], int)
    assert final["zendesk_sla_id"] == 4003  # gold tier
    assert final["portal_account_id"].startswith("acct_")
    assert final["intake_form_url"].startswith(mock_portal_url)
    assert final["pdf_packet_url"].endswith(".pdf")

    # Generated content present
    assert len(final["welcome_email_sequence"]) == 5
    assert "Kickoff Call" in final["kickoff_agenda"]
    assert len(final["readiness_checklist"]) >= 8

    # No errors collected
    assert final["errors"] == []


@pytest.mark.asyncio
async def test_provisioning_is_idempotent_when_rerun(mock_portal_url, monkeypatch):
    """Re-running with the same deal should not blow up; portal account is dedup'd."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    graph = build_graph().compile()
    base: OnboardingState = {"deal_id": "deal-001", "run_id": "x", "events": [], "errors": []}
    a = await graph.ainvoke(base)
    b = await graph.ainvoke(base)
    # Same partner → same portal account id
    assert a["portal_account_id"] == b["portal_account_id"]
