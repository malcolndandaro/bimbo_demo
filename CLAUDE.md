# CLAUDE.md — BimbOps Reviewer / `bimbo-bakery-pipeline`

> **Current deployment (migrated 2026-06-05):** workspace **`fevm-malcoln-aws-stable`** ·
> catalog **`bimbo`** · local profile **`malcoln-aws-stable`** (PAT) · CI service principal
> **`bcc03e5e-15fd-47a2-8da4-ccc3edce34d4`** (M2M OAuth; **not** a workspace admin). The
> GitHub repo is still `malcolndandaro/bimbo_demo` — only the Databricks catalog was renamed
> (`bimbo_demo`→`bimbo`). Run scripts with `DATABRICKS_CONFIG_PROFILE=malcoln-aws-stable`.
>
> Orientation for any engineer or agent opening this repo. Read this first, then `DEMO.md` (this repo), `docs/ado-translation.md`, and — in the local `/bimbo` parent (private, not committed) — `CONTEXT.md`, the 3 ADRs, and `REBUILD.md`.
>
> Repo: `github.com/malcolndandaro/bimbo_demo` (**public** — keep secrets and workspace identifiers out). Workspace: `https://fevm-malcoln-aws-stable.cloud.databricks.com`. Catalog: `bimbo`.
> **Note on language:** code/identifiers are in English; the handbook, agent output, PR comments, and many docstrings are in **Spanish** (domain language for Grupo Bimbo). This CLAUDE.md is in English but preserves Spanish domain and resource names verbatim (e.g. `bimbo_prd`, `bimbops_handbook`, rule `ENV-01`).

## What is the BimbOps Reviewer

The **BimbOps Reviewer** is a retrieval-grounded AI code reviewer for Grupo Bimbo's internal platform team ("BimbOps"). It is a custom **MLflow `ResponsesAgent`** running on **Databricks Model Serving**, grounded on the **BimbOps Handbook** (coding standards) via **Vector Search**, and powered by the native Claude foundation model `databricks-claude-sonnet-4-5`. On every pull request it reads the diff, retrieves the relevant handbook rules, and posts **cited, severity-tagged findings in Spanish** as a PR comment plus a GitHub **Check Run** that gates the merge. It catches the *semantic/policy* problems that deterministic linters and GitHub Secret Scanning cannot — for example, a dev job hardcoding a reference to the production catalog `bimbo_prd`.

This repo (`bimbo-bakery-pipeline`) is the consolidated **end-to-end CI/CD demo**: a sample "bakery" data pipeline plus the full reviewer agent and the GitHub Actions pipeline that reviews, fixes, merges, deploys, and promotes code across `dev → qa → prod`. The reviewer is itself a governed, evaluated, DABs-deployed Unity Catalog asset — it is shipped by the same pipeline it guards (the "agent-as-code" recursion).

## Architecture

Two halves that meet at the serving endpoint.

### The agent (`bimbops_reviewer/`)
- **MLflow `ResponsesAgent` on Model Serving.** Registered to UC as `bimbo.dev.bimbops_reviewer` (alias `@prod`), served at endpoint **`bimbops-reviewer`** (task `agent/v1/responses`). ADR-0001.
- **VS-grounded.** Rules come from the BimbOps Handbook, parsed one-row-per-rule into `bimbo.dev.bimbops_handbook_rules` (CDF) and synced to the Vector Search Delta Sync index `bimbo.dev.bimbops_handbook_rules_idx` on endpoint `bimbops-vs` (embeddings `databricks-gte-large-en`, top `N_RULES=8`).
- **Native Claude.** FM endpoint `databricks-claude-sonnet-4-5`, `temperature=0.0`; review `max_tokens=1800`, fix `max_tokens=4000`.
- **Two modes, one agent.** *Review mode* (auto on every PR) posts cited Spanish findings + a Check Run. *Fix mode* (`/bimbops-fix`, human-triggered) rewrites the offending file(s) and pushes a commit.
- **predict flow** (`agent/agent.py`): diff → `build_review_context` → query VS with the added code itself → `build_review_prompt` → call FM → `parse_review` → return one JSON text item.

### The pipeline (GitHub Actions + DABs)
`PR → review → fix → merge → deploy → promote`:
1. **PR opened/updated** → deterministic gate (`pr-checks.yml`: Ruff + sqlfluff + `bundle validate`) **and** AI review (`bimbops-review.yml`).
2. **`/bimbops-fix` comment** (maintainer) → `bimbops-fix.yml` rewrites the file and pushes one commit to the PR head branch → re-triggers review + checks (self-correcting loop).
3. **Human approval + merge to `main`.**
4. **`deploy.yml`** (push to `main`): `deploy-dev` + serverless integration tests → **qa gate** → `deploy-qa` → **prod gate** → `deploy-prod`.

## Repo map

| Path | Role |
|---|---|
| `bimbops_reviewer/agent/review_core.py` | **Pure functional core** (444 lines, no I/O/SDK/network). Every decision: context builder, prompt builders, finding parser, severity gate, check-run mapper, authz, fix-file selection, content validation, eval scorers. |
| `bimbops_reviewer/agent/agent.py` | MLflow `ResponsesAgent` shell — VS retrieval + FM call. `mlflow.models.set_model(...)`. |
| `bimbops_reviewer/agent/log_model.py` | Register the agent to UC (`code_paths=[review_core.py]`), local pre-deploy validation, move `@prod` alias. |
| `bimbops_reviewer/agent/deploy_agent.py` | `databricks.agents.deploy(...)` to endpoint `bimbops-reviewer`. Version arg: `@prod` alias or numeric pin. |
| `bimbops_reviewer/ci/review_pr.py` | CI review shell: invoke endpoint → Spanish comment + `BimbOps Reviewer` Check Run. Always `sys.exit(0)`. |
| `bimbops_reviewer/ci/fix_pr.py` | CI fix shell: authz → re-review → FM full-file fix → validate → BimbOps Bot pushes one commit to PR head. |
| `bimbops_reviewer/index/` | `build_handbook_index.py` (parse handbook → table + VS index), `verify_retrieval.py` (acceptance queries). |
| `bimbops_reviewer/eval/` | `run_eval.py` (MLflow `genai.evaluate`, 100% regression gate), `scorers.py`, `fixtures.py` + fixtures. |
| `bimbops_reviewer/gateway/` | `configure_gateway.py`, `cost_report.py`, gateway configs, `README.md` (what's enforced live). |
| `bimbops_reviewer/tests/test_review_core.py` | **37 unit tests** over the pure core (no workspace/network). |
| `bimbops_handbook/` | 7 markdown files: README + 6 standards (`catalog-per-env`, `transform-pattern`, `sql-conventions`, `pii-secret-policy`, `naming-conventions`, `dabs-conventions`). 22 rules, the VS knowledge base. |
| `src/` | The "bakery" pipeline code (`src/bakery/transforms.py`, `src/daily_route_profitability.py`). |
| `data/seed_bakery.py` | Synthetic generator for the `fact_sales` / `dim_store` source tables (recovery — regenerate the pipeline inputs if dropped). |
| `src/jobs/pricing_adjustments.py` | Lives on branch `feature/nueva-logica-precios` (PR #1) — holds the **hero ENV-01 violation** at line 27. Not on `main`/`feat/bimbops-reviewer`. |
| `sql/`, `resources/`, `tests/`, `bad-pr/` | SQL assets, DABs job definitions, integration tests, anti-example files. |
| `.github/workflows/` | `pr-checks.yml`, `bimbops-review.yml`, `bimbops-fix.yml`, `deploy.yml`. |
| `databricks.yml` | DABs bundle `bimbo-bakery-pipeline`; targets `dev`/`qa`/`prd`; var `agent_model_version`. |
| `docs/ado-translation.md` (+ 4 `azure-pipelines-*.yml`) | GitHub Actions → Azure DevOps parity (Bimbo's real stack). |
| `README.md` | **STALE** — still the Session-1 "04 — Quality Gate" snippet README. Does not yet describe the E2E repo. |

## How the pipeline works end-to-end

1. **PR opened** on a feature branch (hero: `feature/nueva-logica-precios`).
   - `pr-checks.yml` (`pr-quality-gate`): `ruff` + `sqlfluff` on `ubuntu-latest`; `bundle validate` (dev/qa/prd) on the **self-hosted** runner. Deterministic hard gates owning **syntax**.
   - `bimbops-review.yml`: the reviewer posts a Spanish summary comment + the **`BimbOps Reviewer`** Check Run owning the **semantic** layer. Severity gate (`decide_gate`, ADR-0002): any **BLOCKER → `failure`** (blocks merge once required); SUGGESTION/STYLE only → `neutral`; none → `success`. Annotation levels: BLOCKER=failure, SUGGESTION=warning, STYLE=notice (cap 50).
2. **`/bimbops-fix`** comment by a maintainer → `bimbops-fix.yml`: authz check (write/maintain/admin, non-protected branch, non-fork) → re-review → FM returns the COMPLETE corrected file per finding-bearing file → `validate_content` (must parse; abort the whole push if any file invalid) → **BimbOps Bot** pushes ONE commit to the PR head branch via `BIMBOPS_BOT_TOKEN`. The new commit re-triggers review + checks.
3. **Human approval + merge to `main`.**
4. **`deploy.yml`** (push to `main`, all jobs self-hosted): `deploy-dev` = `bundle deploy -t dev` + serverless `pytest tests/` against `bimbo.dev` → **qa gate** (`environment: qa`, required reviewer) → `deploy-qa` = `bundle deploy -t qa` → **prod gate** (`environment: prod`) → `deploy-prod` = `bundle deploy -t prd` (sandbox schema `bimbo.prod`). `concurrency: deploy-<ref>`, `cancel-in-progress: false`.

## Conventions & hard rules

- **Functional-core / imperative-shell.** All decision logic is pure in `agent/review_core.py` (no I/O, SDK, or network — `import json`/`re` only) and unit-tested. Every side effect (VS query, FM call, GitHub API, git push, UC/serving deploy, SQL) lives in thin shells (`agent.py`, `ci/*.py`, `index/*`, `eval/*`, `gateway/*`). When changing behavior, change the core and a test; keep shells dumb. This is also the Transform pattern Bimbo is taught — porting to Azure DevOps touches only the shell.
- **Severity-gated, never-block review.** Only BLOCKER findings block. The CI scripts **always `sys.exit(0)`** — the **Check Run conclusion is the gate**, not the job exit code. If the endpoint is down, review posts a Spanish "no disponible / no bloquea" fallback and still exits 0. ADR-0002.
- **Changed-file confinement + fork refusal in fix mode.** Fix mode refuses fork PRs, requires write/maintain/admin on a non-protected branch (`is_authorized`, ADR-0003), confines fixes to the PR's changed files (`select_fixable` rejects absolute `/` and parent-escaping `..` paths), and aborts the entire push if any rewritten file fails to parse.
- **Catalog-per-env (demo: schema-per-env).** The demo uses one catalog `bimbo` with schemas `dev`/`qa`/`prod` — which is why running "prod" live is safe. Bimbo's Future-State target is true catalog-per-env (`bimbo_dev`/`bimbo_qa`/`bimbo_prd`). The hero rule **ENV-01** forbids cross-env catalog references.
- **M2M auth + self-hosted runner.** CI authenticates to Databricks via **OAuth M2M** with the dedicated CI SP (`DATABRICKS_AUTH_TYPE: oauth-m2m`; app id `bcc03e5e-15fd-47a2-8da4-ccc3edce34d4` in repo var `DATABRICKS_SP_CLIENT_ID`, OAuth secret in `DATABRICKS_CLIENT_SECRET`). ADR-0001. **The SP is NOT a workspace admin**, so it can only set job `run_as` to *itself* — therefore qa/prd `run_as` in `databricks.yml` must be the SP, not another user (a non-admin SP setting `run_as` to a human errors at deploy). Every Databricks-touching job runs on the **self-hosted runner** (IP allowlisted on the workspace IP ACL); only the pure-Python lint jobs use `ubuntu-latest`.
- **EMU constraint.** The corporate `gh` identity is an Enterprise Managed User and **cannot perform `gh` write operations** on this personal-account repo (merge, approve environments, mark-ready, rerun, edit). Perform GitHub writes via **SSH push** or the **GitHub UI as `malcolndandaro`** — not via the CLI as the corporate identity. `main` has no branch protection, so direct SSH pushes to `main` are allowed for plumbing.
- **Secret hygiene.** Repo is **public**. Never commit secrets or workspace identifiers (SP client_id, org id, SCIM ids — those live in `CONTEXT.md` in the non-git parent and in GitHub repo vars/secrets). Secrets: GitHub Actions secrets `DATABRICKS_CLIENT_SECRET`, `BIMBOPS_BOT_TOKEN`; non-secret config: repo vars `DATABRICKS_HOST`, `DATABRICKS_SP_CLIENT_ID`. The hero finding is deliberately a cross-env reference, **not** a secret, so it can live in a public repo and so it differentiates from GitHub Secret Scanning.
- **Output language.** Agent prompts, comments, summaries, and PR descriptions are in Spanish; code identifiers in English (rule NM-03).

## Live assets (verified 2026-06-05, `fevm-malcoln-aws-stable`)

- **Serving endpoint `bimbops-reviewer`** — `READY`, serving `bimbo.dev.bimbops_reviewer` **v1 @prod** (100% traffic), foundation model **`databricks-claude-opus-4-8`**. AI Gateway **inference-table logging** → `bimbo.dev.bimbops_reviewer_payload`.
- **Vector Search** — endpoint `bimbops-vs` `ONLINE` (STANDARD). Index `bimbo.dev.bimbops_handbook_rules_idx` ready, **22 rows**, DELTA_SYNC/HYBRID, gte-large-en on `content`.
- **Handbook table** `bimbo.dev.bimbops_handbook_rules` + UC volume `bimbo.dev.handbook_volume` (staging for the index build).
- **Seed tables** `bimbo.dev.fact_sales` (5000 rows) + `bimbo.dev.dim_store` (20 rows).
- **Jobs** (`bundle deploy -t dev`): `bimbops_agent_lifecycle` + `daily_route_profitability` (PAUSED) — fresh job IDs on this workspace.
- **UC model** `bimbo.dev.bimbops_reviewer`, alias `@prod` → v1.
- **CI SP grants:** the dedicated CI SP (`bcc03e5e-15fd-47a2-8da4-ccc3edce34d4`) has `USE_CATALOG` on `bimbo` + `SELECT`/`USE_SCHEMA` on `bimbo.dev`.

For **how to recreate any of these if deleted** (shared workspace — assets can vanish), see **`REBUILD.md`** in the local `/bimbo` parent (private). The in-repo `data/seed_bakery.py` regenerates the `fact_sales`/`dim_store` source tables.

## How to deploy / operate

```bash
# Validate the bundle for every target (what CI runs)
databricks bundle validate -t dev   # also -t qa, -t prd

# Deploy (per target)
databricks bundle deploy -t dev      # qa/prd happen via deploy.yml gates

# Build/ship the agent end-to-end (the agent-as-code lifecycle job)
# Tasks: build_index → register_model → deploy_endpoint → run_eval
databricks bundle run bimbops_agent_lifecycle -t dev

# Register the model manually (moves the @prod alias)
DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/log_model.py

# Run unit tests (pure core, no workspace)
pytest bimbops_reviewer/tests/ -v
```

**Config-only redeploy** (re-point the endpoint at a specific UC model version without re-registering): bump the DABs var `agent_model_version` to a numeric version (e.g. `3`) and run the lifecycle job's `deploy_endpoint` task. First-ever endpoint deploy is ~15 min; a version swap is a fast in-place config update. **Never set `agent_model_version` to `""`** — an empty bundle var serializes to a null Terraform list element and the provider panics (`parameters[<nil>] is not a string`); the default `"@prod"` resolves the alias.

## Pointers

- `CONTEXT.md` (parent dir) — single domain-context file: glossary, 12 Session-2 decisions, defaults, build-reality notes, and the workspace identifiers kept out of this public repo.
- `docs/adr/` (parent dir) — **ADR-0001** reviewer as custom Model-Serving agent fronted by AI Gateway; **ADR-0002** severity-gated review; **ADR-0003** fix-mode pushes to PR head via scoped GitHub App identity.
- `docs/ado-translation.md` (+ `docs/azure-pipelines-*.yml`) — GitHub Actions → Azure DevOps parity (Bimbo's real stack); the ADO publish layer is *specified, not yet implemented*.
- `DEMO.md` — the live demo runbook (step-by-step, with talking points and the fallback plan).
- `REBUILD.md` (**local `/bimbo` parent, private — not in this public repo**) — disaster-recovery runbook: recreate every Databricks resource if it's deleted from the shared workspace. The seed step uses `data/seed_bakery.py` (in this repo).
- `bimbops_reviewer/gateway/README.md` — what AI Gateway governance is enforced where (verified live).
