# BimbOps Reviewer — CI/CD E2E con un agente de IA en Databricks

> Demo de CI/CD de extremo a extremo para el equipo de plataforma de Grupo Bimbo
> ("BimbOps"). El protagonista es el **BimbOps Reviewer**: un revisor de código por
> IA que corre como un asset gobernado de Databricks y se integra al pipeline de
> GitHub Actions — revisa PRs, los corrige a pedido, y promueve el código por
> `dev → qa → prod`.

## La idea en una línea

> En cada PR, los linters determinísticos atrapan la **sintaxis** (Ruff, sqlfluff,
> `bundle validate`) y el **BimbOps Reviewer** —un agente que conoce los estándares
> de Bimbo— atrapa lo **semántico/de política** que ninguna herramienta determinística
> ve (p. ej. un job de *dev* que referencia el catálogo de *producción* `bimbo_prd`).
> Solo los hallazgos **BLOCKER** bloquean; el humano sigue aprobando.

## Qué es el BimbOps Reviewer

Un **MLflow `ResponsesAgent`** desplegado en **Databricks Model Serving** (endpoint
`bimbops-reviewer`), aterrizado sobre el **BimbOps Handbook** (22 reglas de estándares)
vía **Vector Search**, y potenciado por **Claude** (`databricks-claude-sonnet-4-5`).

- **Modo review** (automático en cada PR): publica hallazgos **citados, en español** +
  un **Check Run `BimbOps Reviewer`** que gatea el merge por severidad.
- **Modo fix** (`/bimbops-fix`, disparado por un humano): el bot **reescribe el archivo
  y hace push** de un commit a la rama del PR, que re-dispara la revisión (bucle
  auto-correctivo).
- **Agent-as-code:** el revisor se construye/despliega/evalúa con el **mismo pipeline
  que vigila** (un job de DABs lo arma: index → registro UC → deploy → eval).

## El pipeline (GitHub Actions + Databricks Asset Bundles)

```
PR  →  pr-checks (Ruff + sqlfluff + bundle validate)  +  bimbops-review (Check Run por severidad)
    →  /bimbops-fix (el bot corrige y hace push)  →  aprobación humana + merge a main
    →  deploy-dev + tests de integración serverless  →  [gate qa]  →  [gate prod]
```

| Workflow (`.github/workflows/`) | Qué hace |
|---|---|
| `pr-checks.yml` | Linters determinísticos (sintaxis) + `bundle validate` para dev/qa/prd |
| `bimbops-review.yml` | El agente revisa el diff y publica el Check Run gateado por severidad (ADR-0002) |
| `bimbops-fix.yml` | `/bimbops-fix` → el bot reescribe y hace push (identidad propia, ADR-0003) |
| `deploy.yml` | Post-merge: dev + tests → **gate qa** → **gate prod** (GitHub Environments) |

## Estructura del repo

```
bimbops_reviewer/      ← el agente
  agent/               core puro (review_core.py) + ResponsesAgent + log/deploy
  ci/                  shells de CI: review_pr.py (comentario + Check Run), fix_pr.py (push)
  index/               construye la tabla del Handbook + el índice de Vector Search
  eval/                harness mlflow.genai.evaluate (gate de regresión)
  gateway/             configuración y reporte de costo de AI Gateway
  tests/               37 unit tests del core puro
bimbops_handbook/      22 reglas de estándares (la base de conocimiento del agente)
src/                   pipeline "bakery": bakery/transforms.py (Transform pattern) + job
data/seed_bakery.py    generador sintético de las tablas fuente (recuperación)
sql/  resources/  tests/  bad-pr/
docs/                  traducción a Azure DevOps (ado-translation.md + azure-pipelines-*.yml)
databricks.yml         bundle bimbo-bakery-pipeline; targets dev/qa/prd
```

## Cómo correr

```bash
# Linters (lo que corre pr-checks)
ruff check src/ && ruff format --check src/
sqlfluff lint sql/

# Bundle
databricks bundle validate -t dev          # también -t qa, -t prd
databricks bundle deploy   -t dev

# Unit tests del core del agente (sin workspace)
pytest bimbops_reviewer/tests/ -v

# (Re)desplegar el agente de punta a punta — index → registro → deploy → eval
databricks bundle run bimbops_agent_lifecycle -t dev
```

## Documentación

- **`CLAUDE.md`** — orientación completa: arquitectura, mapa del repo, convenciones, assets en vivo.
- **`DEMO.md`** — runbook paso a paso del demo en vivo (con guion en español y plan de respaldo).
- **`docs/ado-translation.md`** — paridad con Azure DevOps (el stack real de Bimbo).
- `CONTEXT.md`, los 3 ADRs y `REBUILD.md` (runbook de recuperación) viven en el workspace local `/bimbo`, fuera de este repo público.

## Notas

- Repo **público** — sin secretos ni identificadores del workspace. Los secretos viven en
  GitHub Actions secrets; la config no-secreta en repo variables.
- El hallazgo estrella del demo es a propósito una **referencia cross-env**, no un secreto
  (Bimbo ya corre GitHub Secret Scanning) — por eso solo un agente con criterio lo atrapa.
- Auth de CI a Databricks por **OAuth M2M** (OIDC federation es el take-home documentado).
  Los jobs que tocan Databricks corren en un **runner self-hosted** (la IP-ACL del workspace
  bloquea los runners hosted de GitHub).
