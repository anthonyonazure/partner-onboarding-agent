"""Typer CLI for triggering an onboarding run."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.table import Table

from onboarding.graph import build_graph
from onboarding.state import OnboardingState
from onboarding.tracing import flush as flush_traces

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
log = structlog.get_logger()


@app.command()
def run(
    deal_id: str = typer.Option(..., "--deal-id", help="HubSpot deal id to onboard"),
    save_log: bool = typer.Option(True, help="Persist event log to out/<run_id>.json"),
) -> None:
    """Run a full onboarding pass for a single closed-won deal."""
    asyncio.run(_run(deal_id, save_log))


async def _run(deal_id: str, save_log: bool) -> None:
    run_id = uuid.uuid4().hex[:10]
    initial: OnboardingState = {
        "deal_id": deal_id,
        "run_id": run_id,
        "events": [],
        "errors": [],
    }

    graph = build_graph().compile()  # in-memory; CLI doesn't need persistence
    console.rule(f"[bold cyan]Onboarding run {run_id} for deal {deal_id}[/]")

    final_state: OnboardingState = {}
    async for event in graph.astream(initial, stream_mode="values"):
        final_state = event
        last_event = (event.get("events") or [{}])[-1]
        if last_event:
            console.print(f"  [green]✓[/] {last_event.get('kind', '?')}")

    console.rule("[bold cyan]Result[/]")
    table = Table(show_header=False, box=None)
    table.add_row("Partner",       str(final_state.get("partner_name")))
    table.add_row("Tier",          str(final_state.get("tier")))
    table.add_row("M365 mailbox",  str(final_state.get("mailbox_upn")))
    table.add_row("SharePoint",    str(final_state.get("sharepoint_url")))
    table.add_row("Zendesk org",   str(final_state.get("zendesk_org_id")))
    table.add_row("Portal acct",   str(final_state.get("portal_account_id")))
    table.add_row("Welcome PDF",   str(final_state.get("pdf_packet_path")))
    table.add_row("Asset URL",     str(final_state.get("pdf_packet_url")))
    console.print(table)

    if save_log:
        out = Path("out") / f"{run_id}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(final_state, default=str, indent=2))
        console.print(f"\n[dim]Event log: {out}[/]")

    flush_traces()


@app.command()
def webhook(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI webhook receiver (HubSpot deal-stage-change)."""
    import uvicorn

    uvicorn.run("onboarding.webhook:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
