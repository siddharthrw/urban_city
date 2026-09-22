"""
Phase 6/8: Streamlit UI wiring City -> Idea -> Validate -> Constraints -> Plan -> Next Steps.

Run with: streamlit run src/app.py
"""
from pathlib import Path

import streamlit as st

from idea import generate_idea
from validate import validate_idea, populate_explanations
from plan import generate_plan
from report import generate_report_markdown

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"

st.set_page_config(page_title="Urban Planning Decision System", layout="wide", page_icon="🏙️", initial_sidebar_state="expanded")

AUTHORITY_LABEL = {
    "primary": "🟢 Current regulation",
    "superseded": "🟡 Superseded (legacy)",
    "unknown": "⚪ Unclassified",
}

CATEGORY_ICON = {
    "housing": "🏠", "commercial": "🏬", "mixed_use": "🏙️", "hospitality": "🏨",
    "transport": "🚉", "green_space": "🌳", "institutional": "🏫",
    "industrial": "🏭", "general": "📍",
}

st.markdown("""
<style>
.step-badge {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    background: #262730; color: #ddd; font-size: 0.8em; margin-right: 6px;
}
.constraint-card {
    border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
    padding: 14px 18px; margin-bottom: 10px; background: rgba(255,255,255,0.02);
}
.report-box {
    border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
    padding: 20px 24px; background: rgba(255,255,255,0.02);
}
img[data-testid="stLogo"] {
    height: 9rem !important;
    width: auto !important;
    max-height: none !important;
    max-width: 95% !important;
}
div[data-testid="stSidebarHeader"] {
    height: auto !important;
    padding-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🏙️ URBAN PLANNING DECISION SYSTEM")
st.markdown(
    '<span class="step-badge">City</span>→ <span class="step-badge">Idea</span>→ '
    '<span class="step-badge">Validate</span>→ <span class="step-badge">Constraints</span>→ '
    '<span class="step-badge">Plan</span>→ <span class="step-badge">Next Steps</span>',
    unsafe_allow_html=True,
)
st.caption("Demo city: **Chennai** · Powered by a local RAG pipeline over real CMDA planning documents + Ollama (qwen2.5:7b)")

with st.sidebar:
    st.image(str(LOGO_PATH), width=220)
    st.divider()
    st.header("📍 City")
    st.write("**Chennai**, Tamil Nadu")
    st.divider()
    st.subheader("📚 Knowledge base")
    st.markdown(
        "🟢 **Second Master Plan (CMA), 2026**\n"
        "primary — land use & zoning\n\n"
        "🟢 **TN Combined Development & Building Rules, 2019**\n"
        "primary — building & development control\n\n"
        "🟡 **Development Control Rules (CMA), 2004**\n"
        "superseded — legacy reference only"
    )
    st.caption("Primary sources are always preferred over superseded ones when both cover the same topic.")
    st.divider()
    st.caption("This is a demo tool — think of it as a smart first read of the rules, not an official green light. Always double-check with CMDA before you build.")

st.subheader("1. Describe your idea")
raw_idea = st.text_area(
    "What do you want to build or propose in Chennai?",
    value="Build a mixed-use residential and retail complex near a metro station",
    height=100,
)

col_run, col_hint = st.columns([1, 4])
with col_run:
    run = st.button("Generate proposal", type="primary", use_container_width=True)
with col_hint:
    st.caption("Try something specific, e.g. \"a hotel near the airport with a runway view\" or \"a warehouse in an industrial zone\".")

if run:
    if not raw_idea.strip():
        st.warning("Please enter an idea first.")
        st.stop()

    progress = st.progress(0, text="Structuring idea...")
    idea = generate_idea(raw_idea)
    progress.progress(20, text="Checking against planning regulations...")
    validation = validate_idea(idea)
    progress.empty()

    total_findings = len(validation.findings)
    if total_findings:
        with st.status(f"Explaining {total_findings} regulation(s) in plain language...", expanded=True) as status:
            def _on_progress(i, total, finding):
                status.write(f"({i}/{total}) {finding.topic.replace('_', ' ').title()}...")

            populate_explanations(idea, validation.findings, on_progress=_on_progress)
            status.update(label=f"Explained all {total_findings} regulations", state="complete")

    progress = st.progress(80, text="Building plan and next steps...")
    result_plan = generate_plan(idea, validation)
    progress.progress(92, text="Writing report...")
    report_md = generate_report_markdown(idea, validation, result_plan)
    progress.progress(100, text="Done")
    progress.empty()

    icon = CATEGORY_ICON.get(idea.category, "📍")
    st.subheader("2. Idea")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.markdown(f"### {icon} {idea.title}")
        st.write(idea.description)
    with c2:
        st.metric("Category", idea.category.replace("_", " ").title())
    with c3:
        st.metric("Constraints checked", len(validation.findings))

    tab_validate, tab_constraints, tab_plan, tab_report = st.tabs(
        ["🔍 Validate", "📋 Constraints Summary", "✅ Plan & Next Steps", "📄 Full Report"]
    )

    with tab_validate:
        if validation.superseded_dropped:
            st.info(
                f"{validation.superseded_dropped} superseded DCR 2004 match(es) were "
                f"suppressed in favor of current regulations on the same topic."
            )
        for f in validation.findings:
            with st.expander(
                f"{f.topic.replace('_', ' ').title()}  —  {AUTHORITY_LABEL.get(f.authority, f.authority)}",
                expanded=False,
            ):
                st.caption(f"📖 Source: {f.source_title}, page {f.page}")
                st.markdown(f"> {f.text}")
                if f.plain_explanation:
                    st.markdown("**💡 What this means for you:**")
                    st.markdown(f.plain_explanation)

    with tab_constraints:
        for c in result_plan.constraints:
            st.markdown(
                f"""<div class="constraint-card">
                <b>{c['topic'].replace('_', ' ').title()}</b> — {AUTHORITY_LABEL.get(c['authority'], c['authority'])}<br>
                <span style="opacity:0.7">{c['citation']}</span>
                </div>""",
                unsafe_allow_html=True,
            )
            if c.get("plain_explanation"):
                with st.expander("💡 What this means for you", expanded=False):
                    st.markdown(c["plain_explanation"])

    with tab_plan:
        st.markdown("**Recommended next steps, in order:**")
        for i, step in enumerate(result_plan.next_steps, start=1):
            st.checkbox(f"{i}. {step}", key=f"step_{i}")

    with tab_report:
        st.markdown(f'<div class="report-box">', unsafe_allow_html=True)
        st.markdown(report_md)
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button(
            "⬇️ Download report (Markdown)",
            data=report_md,
            file_name=f"{idea.title.replace(' ', '_')[:40]}_report.md",
            mime="text/markdown",
        )

    st.success("All done! Take a look at the tabs above — and remember to check the details with CMDA before you commit to anything.")
