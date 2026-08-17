# AI Architecture

This document covers the AI Insights module's provider abstraction, the hybrid-intelligence
boundary (what's deterministic vs. AI-touched), prompt safety, and required environment
variables. For the data model (Insight/Evidence/Feedback tables, the 24-type rule table,
confidence rubric) see `docs/data-model.md`'s "AI Insights" section. For endpoints see
`docs/api.md`'s "AI Insights" section.

## The layering: Rules → Calculations → Evidence → AI interpretation → Human decision

This is the mental model every part of the module is built to enforce, not just describe:

1. **Rules** (`services/alert_rules.py`, `services/insight_engine.py`) — deterministic
   condition checks against recorded data (a threshold crossed, a trend direction, a co-
   occurrence). Never touched by an AI provider.
2. **Calculations** (`services/insight_calculations.py`, `services/production_calculations.py`,
   `services/economics_calculations.py`, etc.) — pure, DB-free arithmetic (trend classification,
   confidence-level derivation, per-unit division). Never touched by an AI provider.
3. **Evidence** (`AIInsightEvidence` rows) — the rules/calculations layer's output, persisted as
   typed, source-cited facts (observed_fact/calculated_metric/correlation/possible_contributor).
   This is what an AI provider is ever shown — never raw database access, never an instruction
   to "figure out what's wrong."
4. **AI interpretation** (`services/ai_providers/`) — strictly optional, strictly downstream:
   phrases the evidence already assembled by steps 1–3 into natural language. Never invents a
   figure, never recalculates one, never runs before steps 1–3 complete.
5. **Human decision** — every insight, alert, and recommendation carries a disclaimer and
   requires review before action. Nothing in this module (or any prior one) changes equipment
   settings, production parameters, chokes, pumps, or pressure — see CLAUDE.md's standing
   guardrail.

## Hybrid intelligence — what's deterministic vs. AI-touched

| Path | Deterministic? | AI-touched? |
|---|---|---|
| `POST /ai-insights/run` (bulk insight generation) | Always | **Never** — even if a provider is configured |
| `seed_wells.py`'s insight-engine run | Always | **Never** |
| `POST /alerts/run` | Always | **Never** |
| `POST /ai-insights/{id}/interpret` | N/A — explicitly AI-only | Always (or `NullProvider`'s deterministic fallback) |
| `POST /ai-insights/assistant` | First — matches ~8 known question templates against real data | Only as a fallback for unmatched questions |
| `GET /ai-insights/daily-brief` | Always computes the 7 sections | Only if `?narrative=true` — narrates the same computed figures |
| `GET /ai-insights/management-summary` | Always computes the 5 answers | Only if `?narrative=true` |
| `POST /what-if/scenarios`, `/preview`, `/rerun`, `/sensitivity` (What-If Simulator) | Always — every formula runs in `services/whatif_calculations.py`, no AI import anywhere in that file | **Never** |
| `POST /what-if/scenarios/{id}/interpret` | N/A — explicitly AI-only | Always (or `NullProvider`'s deterministic fallback) — interprets the scenario's already-stored results, never recalculates |
| `POST /what-if/compare` | Always computes/reads the comparison | Only if `?narrative=true` — narrates the same stored results |
| `POST /reports`, `/preview`, `/regenerate` (all 4 report types) | Always — every section runs through `services/report_calculations.py`, calling existing deterministic functions from other modules | Only for `monthly_management` with `?narrative=true` — narrates the already-computed section data |
| `what_if_scenario` report's `scenario` section | Always — a passthrough of the saved `Scenario`'s own already-computed `results` | **Never** — the report itself never calls an AI provider; the underlying scenario's own separate `/interpret` text is not embedded automatically |

Bulk generation is deliberately never AI-touched: `run_insight_engine()` is called from
`seed_wells.py` with no network dependency, so coupling it to a provider call would make every
seed/test run depend on provider mocking — undermining "the app must fully function with zero
API key configured" in the strongest sense. It's also the reason `/run` is the one AI Insights
endpoint that is **not** rate-limited — rate limiting in this module is scoped specifically to
the paths that can reach an external provider.

## Provider abstraction

`services/ai_providers/` — one interface, five implementations, all synchronous (`httpx.Client`,
not `AsyncClient` — this codebase has zero `async def` routes/services anywhere, confirmed by
grep before writing the first adapter; using sync keeps the AI layer consistent with everything
else rather than introducing the one async code path in the app).

- **`base.py`** — `AIProvider` (abstract, one method: `interpret(prompt: StructuredPrompt) ->
  AIInterpretation`), `StructuredPrompt` (task, the exact data being interpreted, data sources,
  time period, safety constraints), `render_prompt_text()` (the one shared serializer every real
  adapter sends, so the exact same data reaches every provider identically).
- **`null_provider.py`** — `NullProvider`, used when `AI_PROVIDER` is unset or the selected
  provider's key/URL is missing. **Not a stub** — it composes a genuinely useful answer directly
  from the structured data it was given (same data an LLM would receive), so the app is actually
  useful with zero AI configured, not merely non-crashing. Never opens a network connection
  (directly tested).
- **`openai_provider.py`** / **`anthropic_provider.py`** / **`google_provider.py`** — thin REST
  adapters (Chat Completions / Messages / Generative Language APIs respectively) via raw
  `httpx.Client` calls — no SDK dependency added, matching this project's minimal-dependency
  convention (only `httpx`, already present).
- **`local_provider.py`** — targets a configurable OpenAI-compatible base URL (Ollama, LM
  Studio, or similar self-hosted server), no API key required.
- **`factory.py::get_ai_provider(settings)`** — reads `AI_PROVIDER` and returns the matching
  adapter, or `NullProvider` if unset/unconfigured — never raises. `get_ai_provider_dependency`
  is the FastAPI-dependency wrapper, overridden in tests via `app.dependency_overrides` exactly
  like `get_db` — no test ever needs a real API key or makes a real network call (every provider
  adapter is tested with a mocked `httpx.Client.post`).

No real provider is wired up or exercised with a live key in this codebase's test suite or CI —
that's a deliberate scope decision, not an oversight; wiring a real key is a deployment-time
configuration step (see below), not a code change.

## Prompt safety

Every `StructuredPrompt` carries a fixed `AI_SAFETY_INSTRUCTIONS` constant (`base.py`),
prepended to every provider call as the system/constraints message:

> Do not invent data, causes, production values, costs, or equipment conditions. Only use the
> figures and facts provided — do not introduce numbers not present here. Do not present
> estimates as actual, audited financial or production results. If information needed to fully
> answer is missing, say so explicitly. State uncertainty where it exists — never claim a
> confirmed root cause; use "possible contributor," "correlation," or "may be associated with"
> language instead. Never recommend or imply automatic changes to equipment, chokes, pumps,
> pressure, or production rates — recommendations must be framed as decision-support for a human
> to review.

Every `StructuredPrompt.data` dict is built entirely from already-computed application data
(insight summaries, evidence descriptions, KPI figures) — never a raw database dump, and never
user-supplied free text beyond the Assistant's own question (which itself is only forwarded to
a provider after failing to match a known deterministic template).

## Required environment variables

All optional — the app runs fully on the deterministic engine and `NullProvider` with none of
these set. Documented here by name only; real values are never committed (see
`backend/.env.example`).

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `none` (default) / `openai` / `anthropic` / `google` / `local` |
| `OPENAI_API_KEY` | Required only if `AI_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required only if `AI_PROVIDER=anthropic` |
| `GOOGLE_API_KEY` | Required only if `AI_PROVIDER=google` |
| `LOCAL_AI_BASE_URL` | Required only if `AI_PROVIDER=local` — an OpenAI-compatible base URL |
| `LOCAL_AI_MODEL` | Optional, defaults to `llama3` if `AI_PROVIDER=local` |

If `AI_PROVIDER` names a provider whose required key/URL is missing, `get_ai_provider()` falls
back to `NullProvider` rather than raising — an incomplete AI configuration never breaks the app.

## Security notes

- No API key is ever hard-coded anywhere in this codebase — all read from `Settings`
  (`app/core/config.py`), itself sourced from environment variables / `.env` (never committed).
- No sensitive OG-PIOS data beyond what's explicitly needed to answer a specific insight/
  question is ever sent to a provider — `StructuredPrompt.data` is built field-by-field, never a
  raw model/row dump.
- Rate limiting on `/interpret` and `/assistant` (`services/rate_limit.py`) bounds how often a
  paid external API can be hit per user — documented as a basic, single-process, in-memory
  limiter, not a production-grade distributed one.
