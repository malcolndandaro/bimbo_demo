"""Configure AI Gateway for the BimbOps Reviewer (slice 10) — HONESTLY.

Verified live: a custom **agent** serving endpoint (`bimbops-reviewer`,
task `agent/v1/responses`) only supports **inference-table logging** via AI Gateway
— `put-ai-gateway` rejects usage tracking, guardrails, rate limits, and fallback on
this endpoint type ("agent endpoints currently only support inference tables").

So this script applies the supported subset (inference logging) to the agent
endpoint, then RE-READS the endpoint and reports exactly what is enforced (no
over-claiming). The full governance suite (usage + PII/safety guardrails + rate
limits + provider fallback) lives in `fm_gateway_config.json` and must be applied to
a DEDICATED gateway endpoint fronting the foundation model — that's the production
layer (see README.md). The shared `databricks-claude-sonnet-4-5` FMAPI endpoint
cannot be modified, so that gateway endpoint would front Claude as an external/served
model.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/gateway/configure_gateway.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess  # noqa: S404 — databricks CLI applies the gateway config
import sys

ENDPOINT = "bimbops-reviewer"
AGENT_CONFIG = pathlib.Path(__file__).with_name("agent_inference_config.json")


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["databricks", *args], capture_output=True, text=True)  # noqa: S603,S607


def main() -> None:
    cfg = AGENT_CONFIG.read_text(encoding="utf-8")
    apply = _cli("serving-endpoints", "put-ai-gateway", ENDPOINT, "--json", cfg)
    if apply.returncode != 0:
        print("put-ai-gateway (inference-only) failed:\n", apply.stderr[-800:])
        sys.exit(1)

    # Re-read and report EXACTLY what AI Gateway enforces — never claim more.
    got = _cli("serving-endpoints", "get", ENDPOINT, "-o", "json")
    g = (json.loads(got.stdout).get("ai_gateway") if got.returncode == 0 else {}) or {}
    print("AI Gateway enforced on", ENDPOINT, "(custom agent endpoint):")
    print("  inference_table:", bool((g.get("inference_table_config") or {}).get("enabled")))
    print(
        "  usage_tracking :",
        bool((g.get("usage_tracking_config") or {}).get("enabled")),
        "(unsupported on agent endpoints)",
    )
    print("  rate_limits    :", len(g.get("rate_limits") or []), "(unsupported on agent endpoints)")
    print("  guardrails     :", bool(g.get("guardrails")), "(unsupported on agent endpoints)")
    print(
        "\nℹ️  Full suite (usage + PII/safety guardrails + rate limits + fallback) is in "
        "fm_gateway_config.json — apply it to a DEDICATED gateway endpoint fronting the FM "
        "(production layer; see README.md)."
    )


if __name__ == "__main__":
    main()
