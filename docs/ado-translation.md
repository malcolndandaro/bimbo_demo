# BimbOps en Azure DevOps — guía de traducción

El demo corre sobre **GitHub Actions** porque es más rápido de montar un entorno.
El stack real de Bimbo es **Azure DevOps (ADO)**. Este documento demuestra la
paridad: cada workflow de GitHub tiene su pipeline ADO equivalente. **Casi todos**
los gaps son de **sintaxis, no de capacidad** — mismos gates, misma separación de
identidades, mismo agente. La única excepción real es el trigger por comentario de
PR (`/bimbops-fix`): ADO no lo tiene de forma nativa. El camino manual da paridad
*funcional* sin infraestructura extra; la paridad *de trigger* exacta requiere una
Azure Function de relay (~30 líneas). Detalle al final.

## Los cuatro pipelines

| GitHub Actions (`.github/workflows/`) | Equivalente ADO (`docs/`) | Qué hace |
|---|---|---|
| `pr-checks.yml` | `azure-pipelines-equivalent.yml` | Ruff + sqlfluff + `bundle validate` en cada PR |
| `bimbops-review.yml` | `azure-pipelines-bimbops-review.yml` | Agente revisa el diff, comenta y publica el status que bloquea el merge |
| `bimbops-fix.yml` | `azure-pipelines-bimbops-fix.yml` | El bot reescribe el archivo y hace push a la rama del PR |
| `deploy.yml` | `azure-pipelines-deploy.yml` | Deploy dev + tests → promoción aprobada a qa → prod |

## Mapa de conceptos GitHub → Azure DevOps

| Concepto GitHub | Equivalente Azure DevOps | Notas |
|---|---|---|
| `runs-on: self-hosted` (`macos-bimbo`) | **Self-hosted agent pool** (`pool: name: …`) | Bimbo ya corre sus agentes dentro de la red corporativa allowlisted; mapea 1:1 |
| `runs-on: ubuntu-latest` | `pool: vmImage: ubuntu-latest` | Solo para lint puro (sin acceso al workspace) |
| `vars.*` (repo variables) | Variables de pipeline / **variable group** | No secretas; `bimbops-databricks` agrupa `DATABRICKS_HOST`, `DATABRICKS_SP_CLIENT_ID` |
| `secrets.*` | **Secret variables** del variable group (linkeado a Azure Key Vault opcional) | `DATABRICKS_CLIENT_SECRET`, `BIMBOPS_BOT_TOKEN` |
| `secrets.GITHUB_TOKEN` (auto) | `$(System.AccessToken)` (OAuth del build) | Hay que habilitar "Allow scripts to access the OAuth token" |
| GitHub Environments + required reviewers (`qa`, `prod`) | **Environments + Approvals and checks** | Aprobación humana antes de promover; configurada en la UI, no en el YAML |
| `concurrency: cancel-in-progress: false` | Check **"Exclusive Lock"** en el Environment | Un deploy aprobado no se cancela por un push nuevo |
| Branch protection → required status check | **Branch policy** → "Status check" / "Build validation" | Exige que el status del reviewer (y los lints) estén verdes |
| Check Runs API (`failure` bloquea) | **PR Status API** + branch policy sobre ese status | `BLOCKER → "failed"`; solo SUGGESTION/STYLE → `"succeeded"` (ADO no tiene `neutral`); sin hallazgos → `"succeeded"` |
| `pull_request` (opened/synchronize/reopened) | `pr:` trigger (open/push/reopen) | Equivalente directo |
| `push: branches: [main]` | `trigger: branches: include: [main]` | Equivalente directo |
| `workflow_dispatch` (input `pr`) | `parameters:` + ejecución manual | Equivalente directo |
| `issue_comment` (`/bimbops-fix`) | **Service Hook + relay** (sin equivalente nativo) | Ver abajo |
| Auth OIDC (bloqueado en el demo) | **WIF service connection** + `addSpnToEnvironment` | En ADO la federación con Azure SÍ está disponible — es el camino recomendado |
| Auth M2M (lo que corre el demo) | Variable group con `DATABRICKS_CLIENT_ID/SECRET` | Fallback; los scripts leen `DATABRICKS_*` igual en ambas plataformas |

## Identidad del bot: GitHub App ↔ service connection

Es la pieza que más preguntan los equipos de plataforma, así que la dejamos explícita
(ver también `../../docs/adr/0003-fix-mode-github-app-push.md`).

| | GitHub (demo / producción) | Azure DevOps (producción Bimbo) |
|---|---|---|
| **Identidad de push del bot** | Fine-grained PAT (`BIMBOPS_BOT_TOKEN`) → en prod, **GitHub App** "BimbOps Bot" | **Service connection** scoped a código / PAT de *service account* dedicado |
| **Scope del permiso** | "Contents: write" solo a ramas de feature del PR | Permiso "Contribute" en Azure Repos, restringido a ramas de feature |
| **Nunca puede** | Push a `main` ni a ramas protegidas | Idem — la branch policy de `main` lo impide |
| **Auth a Databricks** | SP `sp-bimbops-cicd` (M2M en el demo, OIDC documentado) | Mismo SP vía WIF service connection (`sc-bimbops-<env>`) |

Dos identidades distintas y deliberadamente separadas:
1. **SP de Databricks** (`sc-bimbops-dev/qa/prd` o el client M2M) — autentica al *workspace* para `bundle deploy` y para llamar al endpoint del reviewer.
2. **Identidad de push del bot** (service connection de código / PAT de service account) — autentica a *Azure Repos* para que el commit de la corrección lo firme el bot, no un humano.

En GitHub se ven como `DATABRICKS_CLIENT_SECRET` vs `BIMBOPS_BOT_TOKEN`. En ADO son una WIF service connection vs una service connection (o PAT) de código. La separación de privilegios es la misma.

## El gap del trigger por comentario

La **única diferencia de capacidad de forma**, no de fondo: ADO no tiene un trigger
nativo equivalente a `issue_comment` que reaccione a `/bimbops-fix` escrito en un PR.
Dos formas de cerrarlo, ambas ya contempladas en `azure-pipelines-bimbops-fix.yml`:

1. **Ejecución manual con parámetro `pr`** (primario, sin infraestructura extra).
   Es exactamente el camino `workflow_dispatch` que el demo ya soporta — el humano
   abre el pipeline, mete el número de PR y corre. Cero piezas nuevas.
2. **Service Hook → Azure Function relay** (paridad total con el `/bimbops-fix`).
   Azure DevOps → Project Settings → Service Hooks → evento *"Pull request commented
   on"* → llama a una Azure Function. La Function valida que el comentario contenga
   `/bimbops-fix` (reemplaza el `if: contains(github.event.comment.body, …)`) y que
   el autor tenga permiso, y luego encola el pipeline vía la REST API de ADO. El
   resultado de cara al usuario es idéntico: comenta `/bimbops-fix` en el PR y el bot
   corrige y hace push.

Esto **no es una limitación del agente ni del patrón** — el agente, los cores, la
autorización y el push funcionan igual. Es solo que el "pegamento" del trigger
necesita una Function de ~30 líneas en lugar de venir gratis con la plataforma.

## Qué NO cambia (el punto clave de la demo)

El agente BimbOps Reviewer y toda su lógica son **agnósticos de la plataforma de
CI/CD**. Vive en Databricks Model Serving y se invoca por HTTP. Los *cores* puros
(`decide_gate`, `to_check_run`, `is_authorized`, `select_fixable`, `extract_code`,
`validate_content`, `build_fix_prompt`) no conocen ni GitHub ni ADO. Lo único
específico de plataforma es la **capa de publicación** al final de `review_pr.py` /
`fix_pr.py`:

- **Review**: GitHub Check Runs API ↔ Azure Repos PR Status API
  (`POST .../pullRequests/{id}/statuses?api-version=7.1`, cuerpo
  `{ state, description, context: { name: "quality", genre: "bimbops-reviewer" } }`).
- **Fix push**: `git push` con `x-access-token` (GitHub) ↔ `git push` con PAT/service
  connection contra `dev.azure.com` (ADO). Mismo confinamiento a la rama del PR.

Por eso el patrón *functional-core / imperative-shell* (el mismo que predicamos a
Bimbo con el Transform pattern) paga aquí: portar a ADO toca solo el shell.

> **Estado honesto:** la capa de publicación ADO (PR Status API, push a
> `dev.azure.com`) está **especificada en estos pipelines, no implementada todavía**
> en `review_pr.py` / `fix_pr.py` — hoy ambos publican contra GitHub. Portarla es
> exactamente el trabajo de *shell* descrito arriba; los cores no se tocan. Las
> variables `AZDO_*` / `SYSTEM_ACCESSTOKEN` que setean los YAML ADO son el contrato
> que ese shell consumiría.

## Resumen para Bimbo

> **Casi todos** los gaps entre GitHub y Azure DevOps en este demo son de
> **sintaxis**, no de capacidad: mismos gates, misma separación de identidades,
> mismo agente. La única salvedad es el trigger por comentario `/bimbops-fix`, que
> en ADO no es nativo — el trigger manual ya da paridad *funcional* sin
> infraestructura, y una Azure Function de relay (~30 líneas) cierra la paridad de
> *trigger* exacta.

### Pendientes documentados (no parte de este demo)
- `docs/oidc-via-azure.md` — el camino OIDC `ADO Pipeline → Azure → Databricks SP`
  con WIF (recomendado para producción; reemplaza el M2M del demo).
