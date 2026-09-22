"""
Phase 5/7: Plan + Next Steps generation (LLM-assisted, RAG-grounded).

Takes an Idea (idea.py) and its ValidationResult (validate.py) and produces
a structured Plan: a constraints summary (grounded, cited findings) and a
Next Steps checklist. For each constraint finding, the local LLM writes a
one-line actionable step -- grounded strictly in that finding's retrieved
text, not the model's own knowledge -- plus a fixed set of standard
approval-process steps.
"""
from dataclasses import dataclass, field

from idea import Idea, generate_idea
from llm import chat_json
from validate import ValidationResult, validate_idea, populate_explanations

STANDARD_NEXT_STEPS = [
    "Engage a CMDA-empanelled architect/licensed surveyor to prepare formal drawings.",
    "Apply for Planning Permission / Building Permit through CMDA (or local body as applicable).",
    "Obtain any required NOCs (fire, environment, traffic) based on project scale.",
]

NEXT_STEPS_SYSTEM_PROMPT = """You are an urban planning assistant for Chennai, India.
You will be given a project idea and a list of constraint findings, each with
a topic and a short excerpt of the actual governing regulation text.
For EACH finding, write ONE concise, actionable next-step sentence telling
the applicant what to verify or do about that specific constraint, based
ONLY on the excerpt given (do not invent numbers or rules not in the excerpt).
Always respond in English.
Respond with ONLY a JSON object: {"steps": ["step for finding 1", "step for finding 2", ...]}
in the SAME ORDER as the findings given, one string per finding."""


@dataclass
class Plan:
    idea_title: str
    city: str
    category: str
    constraints: list = field(default_factory=list)   # list of dicts: topic, citation, text
    next_steps: list = field(default_factory=list)     # list of str


def _llm_next_steps(idea: Idea, validation: ValidationResult) -> list:
    if not validation.findings:
        return []

    findings_desc = "\n".join(
        f"{i+1}. Topic: {f.topic}\n   Excerpt: {f.text.strip()[:400]}"
        for i, f in enumerate(validation.findings)
    )
    prompt = f"Idea: {idea.description}\n\nFindings:\n{findings_desc}"

    for attempt in range(2):
        try:
            parsed = chat_json(prompt, system=NEXT_STEPS_SYSTEM_PROMPT)
            steps = parsed.get("steps", [])
            if len(steps) == len(validation.findings):
                return steps
            print(f"  ! LLM returned {len(steps)} steps for {len(validation.findings)} findings, retrying...")
        except Exception as e:
            print(f"  ! LLM next-step generation failed (attempt {attempt + 1}): {e}")

    # Fallback: generic per-topic wording if the LLM call fails or returns
    # a mismatched number of steps.
    return [
        f"Verify compliance with the '{f.topic.replace('_', ' ')}' requirement per {f.source_title} (p.{f.page})."
        for f in validation.findings
    ]


def generate_plan(idea: Idea, validation: ValidationResult) -> Plan:
    constraints = [
        {
            "topic": f.topic,
            "citation": f"{f.source_title} (p.{f.page})",
            "authority": f.authority,
            "text": f.text.strip(),
            "plain_explanation": f.plain_explanation,
        }
        for f in validation.findings
    ]

    next_steps = _llm_next_steps(idea, validation) + STANDARD_NEXT_STEPS

    return Plan(
        idea_title=idea.title,
        city=idea.city,
        category=idea.category,
        constraints=constraints,
        next_steps=next_steps,
    )


if __name__ == "__main__":
    import sys

    raw = " ".join(sys.argv[1:]) or (
        "Build a mixed-use residential and retail complex near a metro station in Chennai"
    )
    idea = generate_idea(raw)
    validation = validate_idea(idea)
    populate_explanations(idea, validation.findings)
    plan = generate_plan(idea, validation)

    print(f"=== PLAN: {plan.idea_title} ===")
    print(f"City: {plan.city} | Category: {plan.category}\n")

    print("Constraints:")
    for c in plan.constraints:
        print(f"  - [{c['topic']}] ({c['authority']}) {c['citation']}")
        print(f"      {c['text'][:180].strip()}")
        if c["plain_explanation"]:
            print(f"      In plain terms: {c['plain_explanation']}")

    print("\nNext Steps:")
    for i, step in enumerate(plan.next_steps, start=1):
        print(f"  {i}. {step}")
