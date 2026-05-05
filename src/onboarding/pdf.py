"""Co-branded PDF welcome packet (Jinja2 → HTML → WeasyPrint → PDF)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_welcome_packet(
    *,
    partner_name: str,
    partner_logo_url: str | None,
    primary_contact_name: str,
    tier: str,
    services: list[str],
    kickoff_agenda: str,
    readiness_checklist: list[str],
    sharepoint_url: str,
    intake_form_url: str,
) -> bytes:
    template = _env.get_template("welcome_packet.html")
    html = template.render(
        partner_name=partner_name,
        partner_logo_url=partner_logo_url,
        primary_contact_name=primary_contact_name,
        tier=tier.title(),
        services=services,
        kickoff_agenda_md=kickoff_agenda,
        readiness_checklist=readiness_checklist,
        sharepoint_url=sharepoint_url,
        intake_form_url=intake_form_url,
    )
    return HTML(string=html, base_url=str(_TEMPLATES_DIR)).write_pdf()
