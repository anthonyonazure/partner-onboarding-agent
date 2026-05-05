"""LLM-generated welcome sequence, kickoff agenda, readiness checklist.

Falls back to deterministic stub content when ANTHROPIC_API_KEY is unset, so the
demo runs end-to-end without credentials. Set the key to get real generations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from onboarding.tracing import traced

MODEL = os.environ.get("ONBOARDING_MODEL", "claude-sonnet-4-6")


@dataclass
class ContentBundle:
    email_sequence: list[dict]
    kickoff_agenda: str
    readiness_checklist: list[str]


_PROMPT = """You are generating onboarding collateral for a new B2B cybersecurity services partner.

Partner: {partner_name}
Primary contact: {primary_contact_name}
Tier: {tier}
Services purchased: {services}

Produce a single JSON object with three keys:

1. "email_sequence" — array of EXACTLY 5 onboarding emails sent over 7 days. Each item has:
     - "day_offset": 0, 1, 3, 5, 7
     - "subject": short, specific, no spam tropes
     - "body": 4-8 short paragraphs in plain text, no greeting fluff, no signature
     - "purpose": one phrase

2. "kickoff_agenda" — markdown for a 45-minute kickoff call agenda. Include time-boxed sections,
   stakeholder asks, and a clear "what success looks like in 30 days" closing block.

3. "readiness_checklist" — array of 8-12 concrete, verifiable items the partner must complete
   before they're considered fully onboarded. Each item is a single imperative sentence.

Tone: confident, technical, peer-to-peer. No marketing fluff. No emojis. Assume the reader is a
CISO or security ops lead.

Return ONLY the JSON object, no preamble.
"""


@traced(name="anthropic.messages.create", as_type="generation")
async def generate_content_bundle(
    *,
    partner_name: str,
    primary_contact_name: str,
    tier: str,
    services: list[str],
) -> ContentBundle:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _stub_bundle(partner_name, primary_contact_name, tier, services)

    client = AsyncAnthropic()
    prompt = _PROMPT.format(
        partner_name=partner_name,
        primary_contact_name=primary_contact_name,
        tier=tier,
        services=", ".join(services) or "(none specified)",
    )
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    # Strip markdown fences if the model wrapped it
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    data = json.loads(text)
    return ContentBundle(
        email_sequence=data["email_sequence"],
        kickoff_agenda=data["kickoff_agenda"],
        readiness_checklist=data["readiness_checklist"],
    )


def _stub_bundle(
    partner_name: str, primary_contact_name: str, tier: str, services: list[str]
) -> ContentBundle:
    services_line = ", ".join(services) if services else "your services"
    return ContentBundle(
        email_sequence=[
            {
                "day_offset": 0,
                "subject": f"Welcome aboard, {partner_name}",
                "body": (
                    f"Hi {primary_contact_name}, this kicks off your onboarding. "
                    f"You're at the {tier} tier with {services_line} in scope. "
                    "You'll get four more emails over the next week."
                ),
                "purpose": "Kickoff acknowledgement",
            },
            {
                "day_offset": 1,
                "subject": "Your shared workspace is live",
                "body": "SharePoint site, Planner board, and shared mailbox are provisioned.",
                "purpose": "Provisioning confirmation",
            },
            {
                "day_offset": 3,
                "subject": "Intake form — please complete this week",
                "body": "Quick 6-field form so we can finalize escalation paths.",
                "purpose": "Information gathering",
            },
            {
                "day_offset": 5,
                "subject": "Kickoff call agenda preview",
                "body": "Attaching the agenda. Read before our session.",
                "purpose": "Meeting prep",
            },
            {
                "day_offset": 7,
                "subject": f"30-day readiness check, {partner_name}",
                "body": "Reviewing the 30-day readiness checklist together on our weekly sync.",
                "purpose": "Milestone gate",
            },
        ],
        kickoff_agenda=(
            "## Kickoff Call (45 min)\n\n"
            "- 0:00–0:05  Introductions & roles\n"
            "- 0:05–0:15  Confirm scope & services in flight\n"
            "- 0:15–0:25  Escalation paths and on-call protocol\n"
            "- 0:25–0:35  SIEM ingest, ticketing handshake\n"
            "- 0:35–0:45  What success looks like at day 30\n\n"
            "**Stakeholder asks**: confirm primary security contact, "
            "share SIEM endpoint, approve runbook templates.\n"
        ),
        readiness_checklist=[
            "Confirm primary security contact and after-hours phone",
            "Share SIEM endpoint and authentication method",
            "Approve incident response runbook templates",
            "Schedule recurring weekly sync (30 min)",
            "Sign off on SLA tier and escalation matrix",
            "Provide ticketing system handshake credentials",
            "Complete intake form (6 fields)",
            "Designate executive sponsor for QBRs",
            "Review and acknowledge data handling policy",
            "Validate first synthetic test alert end-to-end",
        ],
    )
