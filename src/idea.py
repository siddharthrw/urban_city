"""
Phase 3/7: Idea generation module (LLM-backed via local Ollama).

Takes a raw user idea for Chennai and turns it into a structured proposal:
title, category, description, plus the most relevant regulatory/planning
context pulled from the RAG corpus (via retrieve.search) so the proposal is
grounded in real source material before validation (Phase 4).
"""
from dataclasses import dataclass, field

from llm import chat_json
from retrieve import search

CITY = "Chennai"

CATEGORIES = [
    "housing", "commercial", "mixed_use", "hospitality", "transport",
    "green_space", "institutional", "industrial", "general",
]

SYSTEM_PROMPT = f"""You are an urban planning assistant for {CITY}, India.
Given a raw project idea from a user, extract structured fields as JSON with
exactly these keys:
- "title": a short, clean title (max 12 words)
- "category": one of {CATEGORIES}
- "description": a 1-2 sentence rephrasing of the idea, factual, no embellishment
- "search_terms": a short string (5-15 words) of planning/regulatory keywords
  someone would search a building-code/master-plan document for to find rules
  relevant to this idea (e.g. mentioning zoning, height, airport, setbacks,
  environment, heritage, etc. if applicable to THIS idea specifically).
- "location_name": the most specific place/locality/landmark name mentioned
  in the idea (e.g. "Meenambakkam", "Anna Nagar", "T Nagar metro station"),
  or "" if no specific place is mentioned. Extract it verbatim -- do NOT
  guess what area it is or add any commentary, just pull out the name if
  one is stated.
Respond with ONLY the JSON object, no other text."""


@dataclass
class Idea:
    city: str
    raw_text: str
    title: str
    category: str
    description: str
    search_terms: str = ""
    location_name: str = ""
    context: list = field(default_factory=list)


def generate_idea(raw_text: str, k_context: int = 5) -> Idea:
    if not raw_text or not raw_text.strip():
        raise ValueError("Idea text must not be empty")

    parsed = chat_json(raw_text.strip(), system=SYSTEM_PROMPT)

    category = parsed.get("category", "general")
    if category not in CATEGORIES:
        category = "general"
    title = parsed.get("title") or raw_text.strip()[:70]
    description = parsed.get("description") or raw_text.strip()
    search_terms = parsed.get("search_terms", "")
    location_name = parsed.get("location_name", "") or ""

    context = search(search_terms or raw_text, k=k_context)

    return Idea(
        city=CITY,
        raw_text=raw_text.strip(),
        title=title,
        category=category,
        description=description,
        search_terms=search_terms,
        location_name=location_name,
        context=context,
    )


if __name__ == "__main__":
    import sys

    raw = " ".join(sys.argv[1:]) or (
        "Build a mixed-use residential and retail complex near a metro station in Chennai"
    )
    idea = generate_idea(raw)
    print(f"City: {idea.city}")
    print(f"Title: {idea.title}")
    print(f"Category: {idea.category}")
    print(f"Description: {idea.description}")
    print(f"Search terms: {idea.search_terms}")
    print(f"Location name: {idea.location_name or '(none detected)'}")
    print(f"\nRelevant context ({len(idea.context)} chunks):")
    for c in idea.context:
        print(f"  [{c['score']:.3f}] {c['source_file']} (p.{c['page']}, {c['authority']}) - {c['text'][:120].strip()}")
