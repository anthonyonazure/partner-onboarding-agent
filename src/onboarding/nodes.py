"""Per-step nodes for the onboarding graph.

Each node is async, takes state, returns a partial state dict (LangGraph merges).
Idempotent where possible: re-running a node should not re-create resources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from b2b_toolkit import get_adapters

from onboarding.content import generate_content_bundle
from onboarding.pdf import render_welcome_packet
from onboarding.state import OnboardingState
from onboarding.tracing import traced

log = structlog.get_logger()
_OUT = Path("out")
_OUT.mkdir(exist_ok=True)


def _event(kind: str, **detail: Any) -> dict[str, Any]:
    return {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **detail}


@traced(name="read_partner_profile")
async def read_partner_profile(state: OnboardingState) -> dict[str, Any]:
    adapters = get_adapters()
    deal = await adapters.hubspot.get_deal(state["deal_id"])
    company = await adapters.hubspot.get_company(deal["associated_company_id"])
    log.info("node.profile", deal_id=state["deal_id"], company=company["name"])
    return {
        "partner_id": company["id"],
        "partner_name": company["name"],
        "partner_domain": company["domain"],
        "partner_logo_url": company.get("logo_url"),
        "primary_contact_email": company["primary_contact_email"],
        "primary_contact_name": company["primary_contact_name"],
        "tier": company.get("tier", "silver"),
        "region": company.get("region", "NA"),
        "services_purchased": deal.get("services_purchased", []),
        "contract_signed_at": company["contract_signed_at"],
        "events": [_event("partner_profile_loaded", partner=company["name"])],
    }


@traced(name="provision_m365")
async def provision_m365(state: OnboardingState) -> dict[str, Any]:
    adapters = get_adapters()
    name = state["partner_name"]
    alias = state["partner_domain"].split(".")[0].lower() + "-partners"

    mailbox = await adapters.m365.create_mailbox(display_name=f"{name} Partners", alias=alias)
    site = await adapters.m365.create_sharepoint_site(name=f"{name} Workspace", owner_upn=mailbox.upn)
    planner = await adapters.m365.create_planner_board(
        title=f"{name} Onboarding",
        owner_group_id=site.site_id,
        buckets=["Week 1: Provisioning", "Week 2: Kickoff", "Week 3: Activation", "Blockers"],
    )
    return {
        "mailbox_upn": mailbox.upn,
        "sharepoint_site_id": site.site_id,
        "sharepoint_url": site.web_url,
        "planner_plan_id": planner.plan_id,
        "events": [_event("m365_provisioned", upn=mailbox.upn, site=site.web_url)],
    }


@traced(name="provision_zendesk")
async def provision_zendesk(state: OnboardingState) -> dict[str, Any]:
    adapters = get_adapters()
    org = await adapters.zendesk.create_organization(
        name=state["partner_name"],
        domain=state["partner_domain"],
        tier=state["tier"],
    )
    sla_id = await adapters.zendesk.attach_sla_policy(org_id=org.organization_id, tier=state["tier"])
    return {
        "zendesk_org_id": org.organization_id,
        "zendesk_sla_id": sla_id,
        "events": [_event("zendesk_provisioned", org_id=org.organization_id, sla=sla_id)],
    }


@traced(name="provision_portal")
async def provision_portal(state: OnboardingState) -> dict[str, Any]:
    adapters = get_adapters()
    account = await adapters.portal.create_account(
        partner_id=state["partner_id"],
        partner_name=state["partner_name"],
    )
    intake_url = await adapters.portal.create_intake_form(
        account_id=account.account_id,
        fields=[
            "primary_security_contact_name",
            "primary_security_contact_email",
            "preferred_escalation_phone",
            "siem_in_use",
            "ticketing_system",
            "after_hours_protocol",
        ],
    )
    return {
        "portal_account_id": account.account_id,
        "intake_form_url": intake_url,
        "events": [_event("portal_provisioned", account_id=account.account_id)],
    }


@traced(name="generate_content")
async def generate_content(state: OnboardingState) -> dict[str, Any]:
    bundle = await generate_content_bundle(
        partner_name=state["partner_name"],
        primary_contact_name=state["primary_contact_name"],
        tier=state["tier"],
        services=state["services_purchased"],
    )
    return {
        "welcome_email_sequence": bundle.email_sequence,
        "kickoff_agenda": bundle.kickoff_agenda,
        "readiness_checklist": bundle.readiness_checklist,
        "events": [_event("content_generated", emails=len(bundle.email_sequence))],
    }


@traced(name="build_pdf_packet")
async def build_pdf_packet(state: OnboardingState) -> dict[str, Any]:
    pdf_bytes = render_welcome_packet(
        partner_name=state["partner_name"],
        partner_logo_url=state.get("partner_logo_url"),
        primary_contact_name=state["primary_contact_name"],
        tier=state["tier"],
        services=state["services_purchased"],
        kickoff_agenda=state["kickoff_agenda"] or "",
        readiness_checklist=state["readiness_checklist"],
        sharepoint_url=state.get("sharepoint_url") or "",
        intake_form_url=state.get("intake_form_url") or "",
    )
    slug = state["partner_name"].lower().replace(" ", "-")
    out_path = _OUT / f"{slug}-welcome-packet.pdf"
    out_path.write_bytes(pdf_bytes)

    adapters = get_adapters()
    url = await adapters.portal.upload_co_branded_asset(
        account_id=state["portal_account_id"],
        filename=out_path.name,
        content=pdf_bytes,
    )
    # Also drop into SharePoint
    if state.get("sharepoint_site_id"):
        await adapters.m365.upload_file(
            site_id=state["sharepoint_site_id"],
            path=f"/Shared Documents/{out_path.name}",
            content=pdf_bytes,
        )
    return {
        "pdf_packet_path": str(out_path),
        "pdf_packet_url": url,
        "events": [_event("pdf_packet_built", path=str(out_path), url=url)],
    }


@traced(name="post_back_to_hubspot")
async def post_back_to_hubspot(state: OnboardingState) -> dict[str, Any]:
    adapters = get_adapters()
    summary = (
        f"Onboarding completed for {state['partner_name']}.\n"
        f"- M365 mailbox: {state.get('mailbox_upn')}\n"
        f"- SharePoint:   {state.get('sharepoint_url')}\n"
        f"- Zendesk org:  #{state.get('zendesk_org_id')} (SLA {state.get('zendesk_sla_id')})\n"
        f"- Portal acct:  {state.get('portal_account_id')}\n"
        f"- Intake form:  {state.get('intake_form_url')}\n"
        f"- Welcome PDF:  {state.get('pdf_packet_url')}\n"
    )
    await adapters.hubspot.add_note_to_deal(state["deal_id"], summary)
    return {"events": [_event("hubspot_note_posted")]}
