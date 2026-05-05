"""Onboarding graph state. Reducers append to lists, scalars overwrite."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class OnboardingState(TypedDict, total=False):
    # Inputs
    deal_id: str
    run_id: str

    # Resolved partner profile (from HubSpot)
    partner_id: str
    partner_name: str
    partner_domain: str
    partner_logo_url: str | None
    primary_contact_email: str
    primary_contact_name: str
    tier: str
    region: str
    services_purchased: list[str]
    contract_signed_at: str

    # Provisioning results
    mailbox_upn: str | None
    sharepoint_site_id: str | None
    sharepoint_url: str | None
    planner_plan_id: str | None
    zendesk_org_id: int | None
    zendesk_sla_id: int | None
    portal_account_id: str | None
    intake_form_url: str | None

    # Generated content
    welcome_email_sequence: list[dict[str, Any]]
    kickoff_agenda: str | None
    readiness_checklist: list[str]
    pdf_packet_path: str | None
    pdf_packet_url: str | None

    # Logging — appended to via reducers
    events: Annotated[list[dict[str, Any]], add]
    errors: Annotated[list[str], add]
