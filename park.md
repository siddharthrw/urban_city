# Parked work

Ideas and known gaps identified during development but not yet implemented.
Pick back up here when ready.

## #2: Relevance-verification step for retrieval

**Status:** designed, not implemented.

**Problem:** `validate.py` retrieves top-3 candidates per topic by embedding
similarity and blindly takes #1. Similarity measures "these texts talk about
similar concepts," not "this specific rule applies to this specific case."
This is how the `land_use_zoning` topic surfaced a narrow village-catchment
clause instead of a generally-applicable rule (it scored well because it's
genuinely zoning-related text, just the wrong provision) -- flagged by the
user for the "Cafe near Meenambakkam Metro" idea.

**Proposed fix:** after retrieval, add one more LLM call -- a relevance judge
-- that looks at the idea + the top 2-3 candidates for a topic and either
picks whichever actually applies best, or declares "none of these clearly
apply." Batch this into a single call across all topics (like
`_explain_findings` already does) to control latency. When nothing applies,
show "no clearly applicable provision found -- confirm zone classification
directly with CMDA GIS portal" instead of a wrong clause presented with false
confidence.

**Cost:** roughly one more LLM call per `validate_idea()` run (currently ~2:
extra-topics + explanations; would become ~3). Real latency hit, not free.

**Concrete evidence it's needed:** confirmed on 2026-09-17 -- after adding the
deterministic `airport_clearance` topic (see below), its own retrieval pulled
a mediocre match (a generic height-exemption clause on TNCDRBR p.58, not an
actual AAI-NOC clause). The LLM explanation correctly self-flagged it as not
applicable ("you can ignore this for now"), but that means the topic added
close to zero value this run. #2 would let the system either find a *better*
passage for `airport_clearance` or drop the topic instead of surfacing a
placeholder finding.

## #4: Surface retrieval confidence in the UI

**Status:** designed, not implemented.

**Problem:** every finding renders identically (green "Current regulation"
badge) regardless of whether the match was a strong 0.78 similarity or a
mediocre 0.35. No way for the user to tell which findings to trust more.

**Proposed fix:** we already compute `f.score` (cosine similarity, 0-1) per
finding, just don't surface it. Add a badge:
- 🟢 strong match (score > ~0.6)
- 🟡 "Loosely matched -- verify manually" (~0.4-0.6)
- 🔴 "Weak match -- likely doesn't directly apply" (< ~0.4)

Also feed the confidence tier into the explanation prompt so a weak-match
finding's explanation is told to hedge, rather than confidently explaining a
possibly-wrong match.

**Cost:** basically free -- no new LLM calls, just threshold logic + a UI
badge using data already computed.

**Relationship to #2:** #4 is a cheap heuristic safety net (score doesn't
perfectly track "is this the right clause" -- the village clause likely
scored decently since it's genuinely zoning text). #2 is semantically
correct but costs a real LLM call. Reasonable path: ship #4 first, add #2
later if #4 alone doesn't catch enough bad matches in practice.

## Already done (context, not parked)

- **#1 (location grounding via geocoding)** -- implemented in `src/geo.py`,
  wired into `src/validate.py`. Confirmed working: "Meenambakkam" correctly
  geocodes and triggers `airport_clearance` deterministically, independent
  of whether the LLM's training data happens to know that neighbourhood.
- **#3 (stop LLM asserting unverified site facts)** -- tightened
  `EXPLAIN_SYSTEM_PROMPT` in `src/validate.py` and `SUMMARY_SYSTEM_PROMPT` in
  `src/report.py`. Confirmed working: explanation no longer falsely claims
  "since it's in a village area" -- now correctly disqualifies the bad match
  and hedges ("worth checking with CMDA to confirm the exact zone
  classification").

## #5: NVIDIA NIM as hosted LLM provider

**Status:** implemented (`src/llm.py` supports `LLM_PROVIDER=nim`), but
**parked / not the default** -- tested and found slower and less reliable
than local Ollama for our actual pipeline shape, not just theoretically
riskier.

**What's there:** `.env` holds `NVIDIA_API_KEY`; `LLM_PROVIDER=ollama|nim`
switches provider; NIM model defaults to `openai/gpt-oss-20b`
(`NVIDIA_MODEL` / `NVIDIA_MAX_TOKENS` env vars configurable).

**Why it's parked, with real numbers (tested 2026-09-17):**
- Most obvious free-tier model names are dead ends: Llama 3.1/3.3, Mistral-7B,
  Granite, Gemma-3 all returned 410 Gone (retired Aug 2026) or 404 (not
  enabled for this key without extra setup).
- `openai/gpt-oss-20b` is the one that reliably works, but it's a **reasoning
  model** with hidden chain-of-thought tokens -- it needs a large
  `max_tokens` budget or it truncates mid-thought and returns `content: null`.
- `mistral-nemotron` looked promising in isolation (5s, valid JSON) but then
  timed out on every subsequent call (4/4 timeouts at 60s) -- looks like
  free-tier rate limiting kicking in after a few requests.
- **Full pipeline test** (`validate_idea()` on the Meenambakkam cafe idea)
  took **6m28s** end-to-end on NIM vs ~40-60s on local Ollama, and the
  batched explanation call (`_explain_findings`, which asks for one
  explanation per finding in a single call) failed 3 times in a row and fell
  back to no explanations at all -- because that run had 9 topics/findings,
  and gpt-oss-20b's reasoning needs scale with how much it's asked to think
  about per call. 1500 max_tokens was enough for ~5-6 findings in isolated
  tests but not 9.

**The real structural mismatch:** our pipeline deliberately batches multiple
items into single LLM calls (explanations, next-steps) to minimize round
trips. That's exactly the pattern that breaks a reasoning model's fixed
token budget -- more items per call means more hidden reasoning tokens
needed, unpredictably.

**To revisit this later:**
1. Try a much higher `NVIDIA_MAX_TOKENS` (4000+) and see if the batched
   explanation call becomes reliable even with 8-9 findings -- cheapest
   thing to try first.
2. Or restructure `_explain_findings`/`_llm_next_steps` to do one smaller
   call per finding instead of one big batched call -- trades more round
   trips (worse on high-latency hosted APIs) for smaller, more predictable
   reasoning budgets per call. Only worth it if NIM's per-call latency
   becomes competitive with local once explanations aren't batched.
3. Or find a non-reasoning hosted model with reliable free-tier access
   (the search for one was cut short by rate limits/retired models -- worth
   trying again with a fresh key or after some time, or checking NIM's docs
   for which models are currently marked "always free").
4. Current recommendation: stay on local Ollama (`qwen2.5:7b`) as default;
   NIM is wired up and functional as an opt-in (`LLM_PROVIDER=nim` in
   `.env`) for whenever it's worth revisiting.

## Other known rough edges (not yet triaged into a numbered item)

- Adding a 6th+ topic to a single idea makes the batched explanation call
  (`_explain_findings`) more likely to return a mismatched item count on the
  first try (observed: 5-of-6 twice, then succeeded on retry). Existing
  retry logic in `llm.chat_json` / `_explain_findings` absorbs this, but
  worth watching if idea complexity grows further (e.g. multiple landmark
  hits on one idea).
- `docs/doc-extra.md` -- separate parked item: 13 TNCDRBR amendments
  (2020-2025) found, 8 need OCR to be usable, not yet ingested into the
  corpus.
