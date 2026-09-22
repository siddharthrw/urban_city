"""
Phase 8: Detailed report generation.

Assembles the Idea + ValidationResult + Plan into a single structured report:
an LLM-written executive summary (grounded in the actual findings, explicitly
told not to invent facts) plus the full constraints and next steps, formatted
as Markdown for on-screen display and download.
"""
from datetime import date

from idea import Idea
from llm import chat
from plan import Plan
from validate import ValidationResult

SUMMARY_SYSTEM_PROMPT = """You are a friendly urban-planning advisor writing the
opening of a feasibility note for someone in Chennai, India, who wants to build
something. You will be given a project idea and a list of regulatory topics
that were checked. Write a short, warm, easy-to-read summary (3-5 sentences)
in plain conversational English -- like you're talking to a friend who has no
planning background, not writing a government memo. Explain what the project
is, what kinds of rules apply to it, and why they matter in this specific case.
Be clear this is a first-pass check, not an official approval -- but say that
in a normal, reassuring way rather than a legal disclaimer tone. Do not invent
specific numbers or rules that weren't given to you, and do not guess or state
what the actual site's zone classification, urban/rural status, or other real
characteristics are -- you were not given that information. No markdown
headers, no bullet points, no legalese."""


def _executive_summary(idea: Idea, validation: ValidationResult) -> str:
    topics = ", ".join(f.topic.replace("_", " ") for f in validation.findings)
    prompt = (
        f"Idea: {idea.description}\n"
        f"City: {idea.city}\n"
        f"Category: {idea.category}\n"
        f"Regulatory topics checked: {topics}"
    )
    try:
        return chat(prompt, system=SUMMARY_SYSTEM_PROMPT).strip()
    except Exception:
        return (
            f"This is a preliminary screening for a {idea.category.replace('_', ' ')} "
            f"proposal in {idea.city}. The following sections list the regulatory "
            f"constraints identified and the recommended next steps. This is not a "
            f"legal clearance -- verify all items with CMDA before proceeding."
        )


def generate_report_markdown(idea: Idea, validation: ValidationResult, plan: Plan) -> str:
    summary = _executive_summary(idea, validation)
    today = date.today().isoformat()

    lines = []
    lines.append(f"# Urban Planning Feasibility Report")
    lines.append(f"**{plan.idea_title}**")
    lines.append(f"\n*Generated {today} · City: {plan.city} · Category: {plan.category.replace('_', ' ').title()}*")
    lines.append("\n---\n")

    lines.append("## Executive Summary")
    lines.append(summary)

    lines.append("\n## Idea")
    lines.append(f"- **Title:** {idea.title}")
    lines.append(f"- **Category:** {idea.category.replace('_', ' ').title()}")
    lines.append(f"- **Description:** {idea.description}")
    lines.append(f"- **Original request:** \"{idea.raw_text}\"")

    lines.append("\n## Regulatory Constraints Checked")
    if validation.superseded_dropped:
        lines.append(
            f"\n> {validation.superseded_dropped} match(es) from the superseded "
            f"DCR 2004 were suppressed in favor of current (TNCDRBR 2019 / Master "
            f"Plan 2026) regulations on the same topic.\n"
        )
    for c in plan.constraints:
        lines.append(f"\n### {c['topic'].replace('_', ' ').title()}")
        lines.append(f"*Source: {c['citation']} — {c['authority']} regulation*\n")
        lines.append(f"> {c['text']}")
        if c.get("plain_explanation"):
            lines.append(f"\n**What this means for you:**\n\n{c['plain_explanation']}")

    lines.append("\n## Plan & Next Steps")
    for i, step in enumerate(plan.next_steps, start=1):
        lines.append(f"{i}. {step}")

    lines.append("\n## Knowledge Base / Sources")
    lines.append(
        "- Second Master Plan for Chennai Metropolitan Area, 2026 (CMDA) — *primary, "
        "land use & zoning*\n"
        "- Tamil Nadu Combined Development and Building Rules, 2019 — *primary, "
        "building & development control*\n"
        "- Development Control Rules for CMA, 2004 — *superseded, kept only as legacy "
        "reference*"
    )

    lines.append(
        "\n---\n*Heads up: this report is a first-pass, AI-generated read of the rules "
        "from a demo tool — a helpful starting point, not a stamp of approval. Before "
        "you move forward, get a licensed architect and CMDA to confirm everything "
        "against your actual site.*"
    )

    return "\n".join(lines)
