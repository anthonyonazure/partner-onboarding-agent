from onboarding.pdf import render_welcome_packet


def test_pdf_renders_minimum_required_fields():
    pdf = render_welcome_packet(
        partner_name="Test Co",
        partner_logo_url=None,
        primary_contact_name="Pat",
        tier="silver",
        services=["managed-soc"],
        kickoff_agenda="Hello agenda",
        readiness_checklist=["Step one", "Step two"],
        sharepoint_url="https://x/y",
        intake_form_url="https://x/intake",
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5_000  # has content, not just chrome


def test_pdf_renders_with_logo_url():
    pdf = render_welcome_packet(
        partner_name="LogoCo",
        partner_logo_url="https://example.com/missing-logo-doesnt-break-render.png",
        primary_contact_name="Pat",
        tier="gold",
        services=["a", "b", "c"],
        kickoff_agenda="x",
        readiness_checklist=["x"],
        sharepoint_url="https://x",
        intake_form_url="https://x",
    )
    assert pdf.startswith(b"%PDF-")
