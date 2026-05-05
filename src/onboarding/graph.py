"""Wires the onboarding nodes into a LangGraph StateGraph.

Provisioning steps run in parallel where they have no dependency on each other:
M365, Zendesk, and Portal can all kick off after the partner profile is loaded.
PDF packet depends on content + portal account + (optionally) SharePoint site.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from onboarding.nodes import (
    build_pdf_packet,
    generate_content,
    post_back_to_hubspot,
    provision_m365,
    provision_portal,
    provision_zendesk,
    read_partner_profile,
)
from onboarding.state import OnboardingState

CHECKPOINT_DB = "checkpoints.sqlite"


async def _barrier(state: OnboardingState) -> dict:
    """No-op join node. LangGraph's StateGraph treats incoming edges as
    triggers rather than AND-gates; if a node's parents complete in different
    super-steps, the node fires once per super-step. We avoid that by making
    every fan-in converge in the SAME super-step, via this single barrier."""
    return {}


def build_graph():
    g: StateGraph = StateGraph(OnboardingState)

    g.add_node("read_partner_profile", read_partner_profile)
    g.add_node("provision_m365", provision_m365)
    g.add_node("provision_zendesk", provision_zendesk)
    g.add_node("provision_portal", provision_portal)
    g.add_node("generate_content", generate_content)
    g.add_node("await_provisioning", _barrier)
    g.add_node("build_pdf_packet", build_pdf_packet)
    g.add_node("post_back_to_hubspot", post_back_to_hubspot)

    g.add_edge(START, "read_partner_profile")

    # Super-step 1: fan out 4 parallel branches
    g.add_edge("read_partner_profile", "provision_m365")
    g.add_edge("read_partner_profile", "provision_zendesk")
    g.add_edge("read_partner_profile", "provision_portal")
    g.add_edge("read_partner_profile", "generate_content")

    # Super-step 2: ALL four converge in the same super-step → barrier fires once
    g.add_edge("provision_m365", "await_provisioning")
    g.add_edge("provision_zendesk", "await_provisioning")
    g.add_edge("provision_portal", "await_provisioning")
    g.add_edge("generate_content", "await_provisioning")

    # Super-step 3+: linear from here
    g.add_edge("await_provisioning", "build_pdf_packet")
    g.add_edge("build_pdf_packet", "post_back_to_hubspot")
    g.add_edge("post_back_to_hubspot", END)
    return g


async def compile_graph():
    """Compile with a SQLite checkpointer so partial runs can resume.

    Requires `pip install langgraph-checkpoint-sqlite`. The CLI uses an in-memory
    compile() instead; this helper is for the webhook / production path.
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    saver = AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB)
    async with saver as checkpointer:
        return build_graph().compile(checkpointer=checkpointer), checkpointer
