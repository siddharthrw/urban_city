"""
Phase 4/7: Validation engine (LLM-assisted topic selection + RAG grounding).

Takes an Idea (from idea.py) and checks it against the RAG corpus. Runs a
fixed set of universal constraint queries (zoning, FSI, setbacks, parking,
height) plus idea-specific topics proposed by the local LLM (e.g. airport
height/NOC, heritage, coastal zone, environmental clearance -- whatever is
actually relevant to THIS idea), retrieving the most relevant regulatory
passages and surfacing them as structured "constraint findings" per topic.

Authority handling: when both a primary (TNCDRBR 2019 / Master Plan 2026)
and a superseded (DCR 2004) chunk address the same topic, the primary result
is kept and the superseded one is dropped, never the reverse.

The LLM only proposes which topics to look up and phrases the search query --
the actual constraint text shown to the user always comes verbatim from the
retrieved, cited source document, never from the model's own knowledge.
"""
from dataclasses import dataclass, field

from geo import nearby_landmark_topics
from idea import Idea, generate_idea
from llm import chat, chat_json
from retrieve import search

# Constraint topic -> query template, checked for every idea regardless of
# category (universal planning-control axes).
BASE_CONSTRAINT_QUERIES = {
    "land_use_zoning": "permissible land use zone classification",
    "floor_space_index": "floor space index FSI permissible limit",
    "setbacks": "setback requirements front rear side open space",
    "parking": "parking space requirements norms",
    "height_restrictions": "building height restriction maximum",
}

EXTRA_TOPICS_SYSTEM_PROMPT = """You are an urban planning assistant for Chennai, India.
Given a project idea and its category, propose 0-3 ADDITIONAL regulatory topics
(beyond generic zoning/FSI/setbacks/parking/height, which are already checked)
that are specifically relevant to THIS idea -- e.g. airport height/NOC rules,
heritage/conservation zone, coastal regulation zone, environmental clearance,
fire safety for high-occupancy buildings, industrial pollution control, etc.
Only propose a topic if the idea text genuinely suggests it applies.
Respond with ONLY a JSON object: {"topics": [{"key": "short_snake_case_key",
"query": "5-10 word search query for a building-code/master-plan document"}]}
If nothing extra applies, respond {"topics": []}."""

EXPLAIN_SYSTEM_PROMPT = """You are explaining one Indian building regulation
excerpt to a first-time property developer in plain, friendly, everyday
English -- like a knowledgeable friend walking them through it in detail, not
a lawyer or a government notice. You will be given a project idea, a topic
name, and one regulation excerpt taken word-for-word from an official Chennai
planning document.

Write a THOROUGH, DETAILED explanation, not a quick summary. Specifically:
- Go through the excerpt and pull out EVERY specific number, measurement,
  threshold, or distinct requirement it contains -- don't skip any just to
  keep things short. If the excerpt lists multiple cases (e.g. different
  setback distances for different road widths, or different rules for
  different building types), explain each one as its own point, in a short
  bulleted list (use "- " at the start of each line).
- For each point, translate the legal phrasing into plain language AND state
  what it practically means for someone building this specific project.
- Skip only genuine boilerplate (cross-references to other rule numbers,
  procedural filler) that carries no actionable information.
- End with a one-line "**Bottom line:**" sentence summarizing the single
  most important takeaway from this excerpt for this project.
- Do NOT invent numbers or rules that aren't in the excerpt. If the excerpt
  is vague or only partially relevant, say so plainly (e.g. "this section
  doesn't give an exact number for X -- worth double-checking with CMDA").

CRITICAL: You have NOT been told anything about the actual project site's real
characteristics (its true zone classification, whether it's urban or rural,
its exact address, etc.) beyond what's in the idea description. NEVER assert
or guess what kind of area the site is in (e.g. never say "since it's in a
village area" or "since this is a rural zone") -- you have no evidence for
that. If the excerpt seems to be about a narrow or special-case scenario (like
village catchment areas, flood zones, or a specific named area) that may not
match the general case, say plainly that this excerpt might not be the right
provision for this specific site, and that the exact zone/classification
should be confirmed with CMDA -- do not present a possibly-wrong match as if
it definitely applies.

Respond with ONLY the explanation text (markdown bullets where useful) --
no JSON, no preamble like "Here's the explanation", just the content itself."""


@dataclass
class ConstraintFinding:
    topic: str
    query: str
    source_file: str
    source_title: str
    authority: str
    page: int
    score: float
    text: str
    plain_explanation: str = ""


@dataclass
class ValidationResult:
    idea_title: str
    city: str
    findings: list = field(default_factory=list)
    superseded_dropped: int = 0


def _extra_topics(idea: Idea) -> dict:
    prompt = f"Idea: {idea.description}\nCategory: {idea.category}"
    try:
        parsed = chat_json(prompt, system=EXTRA_TOPICS_SYSTEM_PROMPT)
    except Exception as e:
        print(f"  ! LLM extra-topic lookup failed, continuing with base topics only: {e}")
        return {}

    extra = {}
    for t in parsed.get("topics", [])[:3]:
        key = t.get("key")
        query = t.get("query")
        if key and query:
            extra[key] = query
    return extra


def _constraint_queries(idea: Idea) -> dict:
    queries = dict(BASE_CONSTRAINT_QUERIES)
    queries.update(_extra_topics(idea))  # LLM-proposed topics first

    # Deterministic, geocoding-based topics are applied last so they always
    # win on a key collision -- e.g. recognizing that "Meenambakkam" is the
    # airport's own neighbourhood shouldn't depend on the LLM happening to
    # know that, and shouldn't be overridable by a weaker LLM guess either.
    if idea.location_name:
        queries.update(nearby_landmark_topics(idea.location_name))

    return queries


def explain_finding(idea: Idea, finding: ConstraintFinding) -> str:
    """
    Generate the plain-English explanation for one finding. Kept separate
    from validate_idea() (and not called by it) so a caller -- e.g. the
    Streamlit UI -- can generate these one at a time and stream progress to
    the user, rather than blocking on all of them before showing anything.
    """
    prompt = (
        f"Idea: {idea.description}\n"
        f"Topic: {finding.topic.replace('_', ' ')}\n"
        f"Excerpt:\n{finding.text.strip()}"
    )
    for attempt in range(2):
        try:
            explanation = chat(prompt, system=EXPLAIN_SYSTEM_PROMPT).strip()
            if explanation:
                return explanation
        except Exception as e:
            print(f"  ! LLM explanation failed for '{finding.topic}' (attempt {attempt + 1}): {e}")
    return ""  # fall back to showing the raw excerpt only


def populate_explanations(idea: Idea, findings: list, on_progress=None) -> None:
    """
    Fill in .plain_explanation on each finding, in place, one at a time.
    If on_progress is given, it's called as on_progress(index, total, finding)
    before each one starts, so a caller can show live progress.
    """
    total = len(findings)
    for i, f in enumerate(findings, start=1):
        if on_progress:
            on_progress(i, total, f)
        f.plain_explanation = explain_finding(idea, f)


def validate_idea(idea: Idea, k_per_topic: int = 3) -> ValidationResult:
    result = ValidationResult(idea_title=idea.title, city=idea.city)

    for topic, query_template in _constraint_queries(idea).items():
        hits = search(query_template, k=k_per_topic)

        # Prefer primary sources: if a primary chunk exists in the top hits,
        # drop superseded ones for this topic rather than surfacing both.
        primary_hits = [h for h in hits if h["authority"] == "primary"]
        chosen = primary_hits if primary_hits else hits
        result.superseded_dropped += sum(
            1 for h in hits if h["authority"] == "superseded" and primary_hits
        )

        best = chosen[0] if chosen else None
        if best:
            result.findings.append(ConstraintFinding(
                topic=topic,
                query=query_template,
                source_file=best["source_file"],
                source_title=best["source_title"],
                authority=best["authority"],
                page=best["page"],
                score=best["score"],
                text=best["text"],
            ))

    return result


if __name__ == "__main__":
    import sys

    raw = " ".join(sys.argv[1:]) or (
        "Build a mixed-use residential and retail complex near a metro station in Chennai"
    )
    idea = generate_idea(raw)
    result = validate_idea(idea)

    def _progress(i, total, f):
        print(f"  Explaining ({i}/{total}): {f.topic} ...")

    populate_explanations(idea, result.findings, on_progress=_progress)

    print(f"Validating: {result.idea_title} ({idea.category}) in {result.city}\n")
    for f in result.findings:
        print(f"--- {f.topic} ---")
        print(f"[{f.score:.3f}] {f.source_file} (p.{f.page}, {f.authority})")
        print(f.text[:250].replace("\n", " ").strip())
        if f.plain_explanation:
            print(f"  In plain terms: {f.plain_explanation}")
        print()
    print(f"Superseded (DCR 2004) findings dropped in favor of primary source: {result.superseded_dropped}")
