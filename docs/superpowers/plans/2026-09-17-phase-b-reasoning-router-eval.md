# Phase B — Reasoning Router + Eval Harness

> **Date:** 2026-09-17
> **Goal:** Give Hi-EV a reasoning router that chooses the right depth per request, stream responses to the HUD, and measure whether changes make it better or worse. This is the foundation for safe autonomy.
> **Phase A status:** Complete and pushed (`40aaa2b`). See [`memory/hi-ev-phase-a-semantic-memory.md`](../../../memory/hi-ev-phase-a-semantic-memory.md).

---

## Why this phase first

Every later capability depends on two things:
1. **Choosing the right reasoning depth.** A simple status query should not pay for a multi-step agent loop. A high-stakes "should I sign this?" question should not get a one-shot cheap answer.
2. **Knowing whether we improved anything.** Without evals, every prompt change, model switch, or retrieval tweak is guesswork.

Phase B installs the measurement and routing layer that every future phase (proactive alerts, safe autonomy, local voice, tool self-expansion) depends on.

---

## Deliverables

### 1. Reasoning router

**Where:** `src/ev/reasoning/router.py`

**What:** A function `route_request(query: str, context: RequestContext) -> RouteDecision` that classifies an incoming request into one of three paths:

| Path | When | Budget | Examples |
|------|------|--------|----------|
| `fast` | Factual lookup, one tool call, low stakes | 1 cheap LLM call + retrieval | "status of RoboCAD", "what did I decide about X?" |
| `agent` | Multi-step, needs several tools, context-dependent | Up to 5 tool calls, 1–2 LLM calls | "prep me for my 4pm call", "summarize my week across projects" |
| `deliberate` | High stakes, trade-offs, planning, consequences | Planner + reflector loop, cost capped | "should I delay Phase 23 for the patent?", "what could break if I skip this?" |

**How (initial):**
- Start with a **heuristic pre-router** (keyword + history + tool availability) so classification is fast and deterministic.
- Fall back to a **lightweight LLM classifier** only when heuristic confidence is low.
- Add a `cost_budget` and `latency_budget` to each route.
- Return a structured decision: `path`, `reason`, `tools`, `budget`, `confidence`.

**Files to create/modify:**
- `src/ev/reasoning/router.py`
- `src/ev/reasoning/__init__.py`
- `src/ev/server/chat.py` — call router before tool dispatch
- `tests/reasoning/test_router.py`

### 2. Streaming completions

**Where:** `src/ev/llm/client.py` + `src/ev/server/chat.py`

**What:** `LLMClient.complete_stream(...)` yields text deltas. WebSocket `/ws` forwards them as `{type: "delta", text: "..."}` messages and ends with `{type: "done"}`. Keep a non-streaming fallback for tools that need the full response.

**Files to create/modify:**
- `src/ev/llm/client.py` — add `complete_stream()`
- `src/ev/server/chat.py` — stream tool responses and chat answers
- `web/src/lib/bridge.ts` — already supports delta/done events
- `tests/test_llm_client.py` — stream tests
- `tests/test_chat_handler.py` — streaming tests

### 3. Eval harness

**Where:** `tests/eval/`

**What:** A golden-question eval suite grounded in real memory. Each question has a known answer derived from the test database.

**Categories:**
- `status` — project status, current phase, recent decisions
- `memory` — facts the user explicitly remembered
- `research` — web research with citations
- `prep` — meeting prep packets
- `refusal` — dangerous or out-of-scope requests

**Metrics:**
- `correctness` — answer matches ground truth (LLM judge + exact match hybrid)
- `citation_accuracy` — cited sources exist and support the claim
- `latency` — time to first delta and time to done
- `cost` — estimated tokens per path
- `refusal_rate` — appropriately refuses harmful requests
- `hallucination_rate` — claims not in evidence

**Files to create/modify:**
- `tests/eval/conftest.py` — seeded fixtures with known memory
- `tests/eval/test_status_eval.py`
- `tests/eval/test_memory_eval.py`
- `tests/eval/test_research_eval.py`
- `tests/eval/test_prep_eval.py`
- `tests/eval/judge.py` — LLM-as-judge scorer
- `scripts/run_eval.py` — standalone report script

### 4. Guard model / prompt-injection classifier

**Where:** `src/ev/security/guard.py`

**What:** A lightweight classifier that inspects user messages and freshly ingested untrusted text for:
- Prompt injection / jailbreak attempts
- Instructions to ignore system rules
- Requests to downgrade tier or leak secrets
- Work/patent boundary violations

**How:**
- First implementation: rule-based + small LLM call only when rules fire.
- Later: dedicated smaller model or classifier.
- Output: `safe`, `caution`, `blocked` with a reason.
- Auto-downgrade tool tier for content derived from untrusted sources.

**Files to create/modify:**
- `src/ev/security/guard.py`
- `src/ev/security/boundary.py` — integrate guard decisions
- `src/ev/server/chat.py` — run guard before classification
- `tests/test_security.py` — guard tests

---

## Order of work

1. **Eval harness first** — build the measurement tape before changing anything else.
2. **Router** — add routing without changing existing tool behavior; keep fast path default.
3. **Streaming** — add streaming to `LLMClient` and WebSocket; keep non-streaming fallback.
4. **Guard** — add guard checks after routing is stable so it doesn't interfere with eval baselines.
5. **Integrate and measure** — run eval before/after each change; only keep changes that improve scores.

---

## Acceptance criteria

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | `pytest tests/eval/` runs and produces a score report. | Run the command; report prints correctness, latency, cost. |
| 2 | A prompt change that lowers eval score is caught before merge. | CI or pre-commit runs eval on changed prompts. |
| 3 | WebSocket responses stream word-by-word for chat and tool results. | Frontend shows deltas arriving; test asserts multiple delta messages. |
| 4 | Router correctly classifies 20 sample queries into fast/agent/deliberate. | `tests/reasoning/test_router.py` passes with ≥90% accuracy. |
| 5 | Guard blocks known prompt-injection patterns and refuses work-boundary violations. | `tests/test_security.py` guard cases pass. |
| 6 | `python -m pytest` passes with no new warnings. | Full suite. |
| 7 | `ruff check .` clean. | Linter. |

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Eval questions become stale as live memory changes | Ground truth comes from seeded test fixtures, not the live DB. |
| Streaming complicates WebSocket state machine | Add one delta type at a time; keep non-streaming fallback. |
| Router adds latency before the answer | Heuristic pre-router; LLM classification only on low confidence. |
| Guard over-refuses legitimate queries | Start permissive; tune with eval cases; human review blocked cases. |
| LLM-as-judge is itself unreliable | Use exact-match for factual questions and LLM judge only for open-ended synthesis. |

---

## Metrics to track

| Metric | Target by end of Phase B | How to measure |
|--------|--------------------------|----------------|
| Eval pass rate | ≥75% on golden questions | `pytest tests/eval/` |
| Fast-path share | ≥60% of queries routed to fast | Router logs |
| Latency (fast path) | <2s end-to-end | Eval timing |
| Latency (agent path) | <5s for 3 tool calls | Eval timing |
| Streaming time-to-first-delta | <1s after LLM starts | WebSocket test |
| Guard false-positive rate | <5% on benign queries | Manual sample + eval |
| Cost per query | Logged and capped by path | Cost tracking per route |

---

## Follow-up (Phase C preview)

After Phase B, the next layer is **proactive alerts + persistent context**:
- Push deadline/alerts over WebSocket to the HUD.
- Persistent `ChatThread` table + preference learning.
- Morning brief scheduler.

Phase B is the prerequisite because it gives us the router to decide *what* to stream and the eval harness to know *whether* the proactive content is any good.
