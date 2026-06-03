# AI Gateway governance (slice 10)

## What's enforced where (verified live, 2026-06-03)

The BimbOps Reviewer is a **custom agent** serving endpoint (`bimbops-reviewer`,
task `agent/v1/responses`). On agent endpoints Databricks AI Gateway **only supports
inference-table logging** — `put-ai-gateway` rejects usage tracking, guardrails, rate
limits, and fallback (error: *"Usage tracking is not currently supported for this
endpoint type"*; docs: *"agent endpoints currently only support inference tables"*).

| Feature | Agent endpoint (`bimbops-reviewer`) | Dedicated FM gateway endpoint |
|---|---|---|
| Inference-table payload logging | ✅ enabled → `bimbo_demo.dev.bimbops_reviewer_payload` | ✅ |
| Usage tracking (tokens/cost) | ❌ unsupported on agent endpoints | ✅ |
| PII / safety guardrails | ❌ unsupported on agent endpoints | ✅ (input + output) |
| Rate limits | ❌ unsupported on agent endpoints | ✅ |
| Provider fallback | ❌ n/a | ✅ (external models) |

We do **not** claim guardrails/rate-limits are active on the agent endpoint —
`configure_gateway.py` re-reads the endpoint and reports exactly what is enforced.

## Files
- `agent_inference_config.json` — applied to `bimbops-reviewer` (inference logging only).
- `configure_gateway.py` — applies it, then re-reads + reports the enforced config.
- `fm_gateway_config.json` — the FULL governance suite (usage + PII/safety guardrails +
  rate limits) for a DEDICATED gateway endpoint fronting Claude (the production layer).
- `cost_report.py` — cost/usage + recent-traces view from the inference table.

## Production layer (out of scope for the demo on the agent endpoint)
The full suite requires a dedicated AI Gateway endpoint fronting the FM — the shared
`databricks-claude-sonnet-4-5` FMAPI endpoint can't be modified. Create it as an
external/served Claude endpoint configured with `fm_gateway_config.json`, then point the
agent's `LLM_ENDPOINT` at it; guardrails / rate-limits / usage / fallback then genuinely
apply. Prior art in this workspace: `ai-gw-claude-governed`.
