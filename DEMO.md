# DEMO.md — BimbOps Reviewer, live E2E walkthrough

> **Audience:** Grupo Bimbo's BimbOps platform team (owner: **Roberto Adela**; exec sponsor: **Paco**, likely async). **Presenter:** Malcoln Dandaro (Databricks STS).
> **Duration:** ~60 min. **Everything in this demo is in Spanish** (comments, agent output) — narrate in Spanish to match.
> **Workspace:** `https://e2-demo-field-eng.cloud.databricks.com` · **Repo:** `github.com/malcolndandaro/bimbo_demo` (public).
> If a resource is missing/broken before the demo, see **`REBUILD.md`** (in your local `/bimbo` workspace, private).

---

## What we built (read this if you've lost the thread)

A single **continuous E2E CI/CD pipeline** on the live `bimbo_demo` repo, whose new hero is the **BimbOps Reviewer** — a custom AI code reviewer that runs as a governed Databricks asset:

- It's an **MLflow `ResponsesAgent` on Model Serving** (endpoint `bimbops-reviewer`), grounded on the **BimbOps Handbook** (22 standards rules) via **Vector Search**, powered by **Claude** (`databricks-claude-sonnet-4-5`).
- On every PR it posts **cited findings in Spanish** + a **`BimbOps Reviewer` Check Run** that gates the merge by severity (only BLOCKER blocks).
- A maintainer can comment **`/bimbops-fix`** and the bot **rewrites the offending file and pushes** a fix commit, which re-runs the review automatically.
- After merge, `deploy.yml` runs **dev + integration tests → qa gate → prod gate** with human approvals at each promotion.
- The headline: **the reviewer is itself shipped by the same pipeline it guards** (agent-as-code in DABs).

**The hero violation:** a dev job reads the **production catalog `bimbo_prd`** — `spark.read.table("bimbo_prd.gold_pricing")`. This is **deliberately not a secret** (Bimbo already runs GitHub Secret Scanning, so a secret finding would be undifferentiated) and **not even a syntax error** — every deterministic linter passes. Only a **standards-aware** agent catches a cross-env policy violation. The reviewer flags it as a **BLOCKER under rule ENV-01**.

**The labor split (the key talking point):** the deterministic linters (Ruff, sqlfluff, `bundle validate`) **all pass** — this PR is syntactically clean. The **BimbOps Reviewer is the sole blocker**: BLOCKER = the `bimbo_prd` cross-env read (ENV-01); SUGGESTIONs = Transform-pattern smells in `apply_price_adjustments` (`.collect()` to the driver = TP-02, `sys.argv` read inside the transform = TP-04, a table read inside the transform = TP-01); plus a SQL-01 STYLE note on the dashboard view. So `/bimbops-fix` alone takes the PR fully green.

---

## Pre-demo checklist (DO THIS BEFORE THE MEETING)

> ⚠️ **Must prepare beforehand** — items marked **[PREP]** are not part of the live flow. Run the health-check block at the top of `REBUILD.md` (in `/bimbo`) to confirm all Databricks assets exist.

- [ ] **[PREP] Hero PR is open and clean.** Confirm **PR #1** (`feature/nueva-logica-precios` → `main`, "feat: agregar lógica de ajustes de precio y dashboard") is **OPEN**, head is the clean commit based on current `main`, and the cross-env read `spark.read.table("bimbo_prd.gold_pricing")` is present at `src/jobs/pricing_adjustments.py:21`. Expected on a fresh run: Ruff/sqlfluff/bundle-validate **green**, `BimbOps Reviewer` **red (ENV-01 BLOCKER)**. If you already ran `/bimbops-fix` or merged in a rehearsal, reset the branch to `main` + the two hero files again (or ask Claude to). *(PR #3 `demo/env-blocker` was a throwaway gate test — keep it closed.)*
- [ ] **Self-hosted runner `macos-bimbo` is UP** and listening (GitHub → repo → Settings → Actions → Runners shows it green). Every Databricks-touching job needs it; hosted runners are IP-ACL-blocked. Start it with `./run.sh` from `~/Work/Projects/actions-runner` if offline.
- [ ] **Serving endpoint `bimbops-reviewer` is warm/READY.** Check: `databricks serving-endpoints get bimbops-reviewer` → `state.ready=READY`, v3 @ 100%. `scale_to_zero=false`, so it should stay warm — but hit it once to be sure.
- [ ] **Logged into GitHub UI as `malcolndandaro`** in the browser (EMU: approvals and merges go through the UI as this identity, not `gh` as the corporate account).
- [ ] **Vector Search `bimbops-vs` ONLINE**, index `bimbops_handbook_rules_idx` ready (22 rows). `databricks vector-search-indexes get-index bimbo_demo.dev.bimbops_handbook_rules_idx`.
- [ ] **Workspace reachable** and you're authenticated (`DATABRICKS_AUTH_STORAGE=plaintext` profile against `e2-demo-field-eng`).
- [ ] **GitHub Environments `qa` and `prod`** exist with `malcolndandaro` as required reviewer.
- [ ] **Secrets present** in the repo: `DATABRICKS_CLIENT_SECRET`, `BIMBOPS_BOT_TOKEN`. Vars: `DATABRICKS_HOST`, `DATABRICKS_SP_CLIENT_ID`.
- [ ] **[PREP] Backup recording ready.** Per Session-1 precedent (and for Paco watching async), have a pre-recorded full run cued so a live failure never sinks the meeting.
- [ ] **Optional warm-up tabs open:** the AI Gateway/inference-table cost view, the MLflow eval experiment, the `bimbops_agent_lifecycle` job page.

---

## Demo narrative arc

> *Hook → the pain → the fix → the recursion → the take-home.*

1. **The pain** (30 sec): vendors write much of Bimbo's code and skip the Wiki; today's gate catches syntax (Ruff/sqlfluff) and platform (`bundle validate`) but **nothing catches semantic/policy** problems, and release testing is a manual human bottleneck on Roberto.
2. **Open the hero PR** → linters go green on syntax, but the **BimbOps Reviewer flags a BLOCKER** the existing tools provably can't catch.
3. **`/bimbops-fix`** → the agent rewrites the file and pushes; the review **re-runs green** by itself.
4. **Merge → deploy → promote** with human gates (hand Roberto the button).
5. **Extra wow:** cost/governance via AI Gateway, the MLflow eval harness, and the agent-as-code recursion.
6. **Take-home:** the Azure DevOps translation (Bimbo's real stack).

---

## The steps

### Step 0 — Frame the problem (no clicks)

- **Say:** "Hoy su gate atrapa *sintaxis* — Ruff, sqlfluff — y *plataforma* con `bundle validate`. Lo que no atrapa nadie es lo *semántico*: que un job de dev apunte a producción, o que el código ignore el Transform pattern. Y la prueba de release sigue cayendo en una persona. Vamos a poner un revisor con criterio como primer filtro, antes de los humanos."
- **Expected:** room agrees this is the gap.

### Step 1 — Show the hero PR and let the linters pass

- **Do:** open **PR #1** in the browser.
- **URL:** `https://github.com/malcolndandaro/bimbo_demo/pull/1`
- **Say:** "Un dev junior, en su primer mes, abrió este PR con nueva lógica de precios. Sintácticamente está impecable — Ruff, sqlfluff y `bundle validate` pasan en verde." Open `src/jobs/pricing_adjustments.py` in the Files tab and point at **line 21**: `spark.read.table("bimbo_prd.gold_pricing")`.
- **Say (the differentiation beat):** "Fíjense: esto **no es un secreto** —su GitHub Secret Scanning ya cubre eso— y **ni siquiera es un error de sintaxis**: todos los linters pasan. Es un job de **dev** leyendo el catálogo de **producción** `bimbo_prd`. Ninguna herramienta determinística lo atrapa. Esto solo lo ve algo que **conoce sus estándares**."
- **Expected:** `pr-quality-gate` checks (Ruff, sqlfluff, `databricks bundle validate`) are all **green**.

### Step 2 — The BimbOps Reviewer posts its findings

- **Do:** scroll to the PR conversation; show the **Spanish review comment** and the **`BimbOps Reviewer` Check Run** (red / failing). Click into the Checks tab to show the line annotations.
- **Say:** "El revisor leyó el diff, recuperó las reglas relevantes del **BimbOps Handbook** por Vector Search, y publicó **5 hallazgos citados, 1 BLOCKER**. El **BLOCKER**: regla **ENV-01** (línea 21), cita `BimbOps Handbook › Catalog-per-Env › ENV-01` — leer `bimbo_prd` desde dev. Las **SUGGESTIONs** son del Transform pattern en `apply_price_adjustments`: `.collect()` al driver (TP-02), lee `sys.argv` dentro del transform (TP-04), y lee una tabla dentro del transform (TP-01). Más una nota **STYLE** de SQL (SQL-01)."
- **Say (severity gate):** "Solo el BLOCKER bloquea el merge. SUGGESTION y STYLE son consejos. Como los linters ya pasaron, **el agente es el único que bloquea** — atrapó algo con criterio que ninguna herramienta determinística ve. Sigue siendo un *primer filtro*; el humano aprueba. Dos capas de defensa." (ADR-0002)
- **Expected:** red `BimbOps Reviewer` Check Run = `failure`; cited Spanish comment with 5 findings visible. (Note: it blocks the merge *button* only once the check is added as a required status check on `main` — ADR-0002 graduation; otherwise it's advisory-red.)

### Step 3 — Trigger the autofix with `/bimbops-fix`

- **Do:** in the PR comment box, type **`/bimbops-fix`** and submit (UI, as `malcolndandaro`).
- **Say:** "Ahora le pido al mismo agente que lo arregle. Verifica que quien comenta tenga permiso de escritura, que no sea un fork, que no sea una rama protegida — y reescribe **solo los archivos del PR**."
- **Expected:** `bimbops-fix` workflow starts on the self-hosted runner. Watch it at `https://github.com/malcolndandaro/bimbo_demo/actions`.

### Step 4 — The bot pushes a fix and the review re-runs green

- **Do:** wait for the **BimbOps Bot** commit to appear on the PR; the new commit auto-triggers `bimbops-review` + `pr-checks`.
- **Say:** "El bot — identidad propia, vía un PAT fine-grained en el demo, un **GitHub App** en producción (ADR-0003) — hizo **un commit** a la rama del PR: parametrizó el catálogo con una variable de DABs y refactorizó la función a un `df->df` puro. El push **re-dispara** la revisión. Bucle auto-correctivo."
- **Expected:** new commit by BimbOps Bot; the `BimbOps Reviewer` Check Run re-runs and goes **green** (`success`).

### Step 5 — Approve and merge

- **Do:** approve the PR and click **Merge** in the GitHub UI (as `malcolndandaro`).
- **Say:** "El humano sigue siendo el que aprueba. El agente le quitó el trabajo mecánico, no la decisión."
- **Expected:** PR #1 merges to `main`; this triggers `deploy.yml`.
- **EMU note:** do the merge **in the UI** — `gh` writes are blocked under the EMU policy. (A direct SSH push to `main` also works but loses the PR-merge narrative.)

### Step 6 — deploy-dev + serverless integration tests

- **Do:** open Actions → the `deploy` run. Watch `deploy-dev`.
- **URL:** `https://github.com/malcolndandaro/bimbo_demo/actions`
- **Say:** "Al mergear a `main`, arranca el deploy. Primero `dev`: `databricks bundle deploy -t dev` y luego los **tests de integración en serverless** con Databricks Connect contra `bimbo_demo.dev`. Si fallan, no avanza."
- **Expected:** `deploy-dev` green; pipeline pauses at the **qa** environment gate. *(If the run sits `queued`, the self-hosted runner is asleep — wake it.)*

### Step 7 — Approve the qa gate (hand Roberto the button)

- **Do:** in the Actions run, the `deploy-qa` job shows **"Review pending"**. Click **Review deployments → qa → Approve and deploy** (UI, as `malcolndandaro` — or literally hand the screen to Roberto).
- **Say (to Roberto):** "Roberto, este botón es tuyo. Hoy esta validación de release cae sobre ti manualmente — aquí es un gate explícito, auditable, con el agente como primer filtro antes de tu aprobación."
- **Expected:** `deploy-qa` runs `bundle deploy -t qa` (schema `bimbo_demo.qa`); pipeline pauses at the **prod** gate.

### Step 8 — Approve the prod gate

- **Do:** approve the **prod** environment gate the same way.
- **Say:** "Y aquí prod. Es seguro correrlo en vivo porque el demo usa **schema-per-env** en un catálogo sandbox (`bimbo_demo.prod`). En Bimbo la recomendación Future-State es **catalog-per-env** real (`bimbo_prd`) — mismo patrón, aislamiento más fuerte."
- **Expected:** `deploy-prod` runs `bundle deploy -t prd` → deploys to `bimbo_demo.prod`. Full cascade green.

---

## Extra wow (if time)

### A. AI Gateway / cost-per-PR

- **Do:** show the inference table `bimbo_demo.dev.bimbops_reviewer_payload` (or run `python bimbops_reviewer/gateway/cost_report.py`).
- **Say:** "Cada revisión queda **registrada y trazada** vía AI Gateway. Podemos sacar reviews/día, latencia y costo estimado por PR." **Be honest:** the agent endpoint supports **inference-table logging only**; the full governance suite (rate limits, PII guardrails, usage tracking, fallback) is for a dedicated FM gateway endpoint. The token/USD figures in the report are an illustrative lower bound, not real billing.

### B. MLflow eval harness

- **Do:** show `bimbops_reviewer/eval/` and the eval experiment in MLflow.
- **Say:** "El revisor no es 'confía en mí'. Hay un **harness de evaluación**: `mlflow.genai.evaluate()` con scorers que verifican que atrapa el cross-env (ENV-01), marca el anti-patrón de transform, y **cero falsos positivos** en código limpio. Es un **gate de regresión** — si algún scorer baja de 100% en los fixtures, el job falla. Los falsos BLOCKER son nuestra mayor preocupación, y esto los vigila."

### C. The agent-as-code recursion

- **Do:** open the `bimbops_agent_lifecycle` job in the workspace Jobs UI (job id `1063556379578511`).
- **Say:** "El titular: **el revisor se despliega con el mismo pipeline que vigila.** Está en DABs — 4 tareas: `build_index → register_model → deploy_endpoint → run_eval`. Es un asset gobernado de Unity Catalog: versionado, evaluado, con linaje. Para una nueva versión, hacemos un **config-only redeploy**: subimos `agent_model_version` y el endpoint se reapunta en sitio."

---

## Fallback / backup plan

- **If the live run fails** (endpoint cold, runner offline, GitHub Actions hiccup): switch to the **pre-recorded backup run** (cued per the pre-demo checklist). The core arc — PR → review → `/bimbops-fix` → green → merge → deploy → promote — is what must always land.
- **If a resource is missing** (shared workspace — someone deleted a catalog/endpoint/index): see **`REBUILD.md`** (in `/bimbo`) for the dependency-ordered recreate commands. The `bimbops_agent_lifecycle` job rebuilds most of the agent stack in one run; `data/seed_bakery.py` regenerates the source tables.
- **If only the endpoint is slow:** the review is advisory by design (CI always exits 0); if it posts the "no disponible / no bloquea" fallback comment, narrate that as the **graceful-degradation** story — the gate never hard-fails a PR on infra flakiness.
- **If a gate approval stalls:** `concurrency: cancel-in-progress: false` means an approved mid-deploy run is never killed; just re-approve in the UI.
- **Keep `main` and `feat/bimbops-reviewer` clean** — do the demo on the hero PR branch only.

## Take-home: Azure DevOps

- **Do:** point to `docs/ado-translation.md` (+ the 4 `azure-pipelines-*.yml`).
- **Say:** "Esto corre en GitHub Actions por velocidad de montaje, pero su stack es **Azure DevOps**. Casi todos los gaps son de **sintaxis, no de capacidad**: mismos gates, misma separación de identidades, mismo agente — porque el agente vive en Databricks y se llama por HTTP. La única salvedad es el trigger por comentario `/bimbops-fix`: el trigger manual da paridad funcional, y una Azure Function de ~30 líneas cierra la paridad exacta. Honestidad: la capa de publicación a ADO está *especificada, no implementada todavía*." Also mention OIDC federation as the production auth take-home (replacing the demo's M2M).
