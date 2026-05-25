# 04 — Quality Gate de CI/CD (Ruff + sqlfluff + bundle validate)

> Implementa la recomendación **R01 (Code Quality Scoring)** y **R07 (DABs
> validate como required status check)** del assessment Databricks 2026-05.
> Tres herramientas, un solo gate, bloqueo automático de PRs.

## La idea en una línea

> Cada PR ejecuta Ruff (Python), sqlfluff (SQL) y `databricks bundle validate`
> en paralelo. Cualquiera de los tres en rojo → status check rojo → merge
> bloqueado por branch protection.

## Las tres herramientas y qué cubren

| Herramienta | Qué valida | Velocidad |
|-------------|------------|-----------|
| **Ruff** | Estilo, bugs comunes, security (bandit subset), modernización de sintaxis Python | < 1s en repos medianos |
| **sqlfluff** | Estilo SQL (dialect=databricks): capitalización, alias con `AS`, identifiers consistentes, orderings por ordinal | < 5s en cientos de archivos |
| **databricks bundle validate** | Sintaxis de `databricks.yml`, existencia de recursos referenciados, permisos de `run_as`, targets bien formados | 5–15s con autenticación |

Los tres son **complementarios, no superponibles**.

## Estructura del proyecto

```
04-ci-quality-gate/
├── databricks.yml                       ← DABs bundle definition
├── resources/jobs/
│   └── daily_route_profitability.job.yml
├── src/jobs/
│   └── daily_route_profitability.py    ← orquestación que llama a snippet 01
├── sql/
│   └── daily_summary.sql               ← SQL bien formateado (passes sqlfluff)
├── pyproject.toml                       ← config de Ruff
├── .sqlfluff                            ← config de sqlfluff (dialect=databricks)
├── .github/workflows/
│   └── pr-checks.yml                    ← workflow GHA (LO QUE DEMOSTRAMOS)
├── docs/
│   └── azure-pipelines-equivalent.yml  ← misma forma en Azure DevOps
├── bad-pr/                              ← anti-ejemplos para el demo
│   ├── bad_python.py
│   ├── bad_sql.sql
│   ├── bad-databricks.yml
│   └── README.md
└── README.md (este archivo)
```

## Cómo se ve la demo

1. **Estado verde:** correr los 3 linters localmente sobre `src/` y `sql/`.
   Todos pasan.

   ```bash
   ruff check src/
   sqlfluff lint sql/
   databricks bundle validate -t dev
   ```

2. **Estado rojo:** correr los 3 linters sobre `bad-pr/`. Cada uno arroja
   su propio set de errores.

   ```bash
   ruff check bad-pr/bad_python.py
   sqlfluff lint bad-pr/bad_sql.sql
   databricks bundle validate --config-file bad-pr/bad-databricks.yml
   ```

3. **En GitHub:** un PR que incluya los archivos de `bad-pr/` aparece con
   los 3 status checks en rojo. El merge button está bloqueado por
   branch protection rule.

## Lo que Bimbo tiene que cambiar para adoptar esto

| Pieza | Esfuerzo | Bloqueador |
|-------|----------|------------|
| Crear `pyproject.toml` y `.sqlfluff` en cada repo | Bajo | Ninguno |
| Convertir `pr-checks.yml` a `azure-pipelines.yml` | Bajo | Ya hay template (`docs/`) |
| Habilitar branch protection con required checks | Bajo | Permisos de ADO admin |
| OIDC federation para `bundle validate` en CI | Medio | R12, Wave 3 |
| Migrar DataLake Cloud y RTM al template v2 | Medio | R04, Wave 1 |

## Anti-patterns a evitar

- ❌ **Linter "informativo" sin bloqueo.** Si el check no es *required*, los
  devs aprenden a ignorarlo. Bloquear desde el día 1.
- ❌ **Umbral cero al inicio.** Activar `select = [...]` con muchos códigos
  el primer día genera resentimiento. Empezar mínimo (E, F) y endurecer
  cada sprint.
- ❌ **Excluir directorios sin justificación.** Si excluyes `legacy/`,
  documenta cuándo se va a limpiar.

## Cómo se conecta con el resto

- **01-transform-pattern** — el código Python que Ruff valida.
- **02-auth-recommended** — OIDC federation autentica el `bundle validate`
  step sin client_secret.
- **05-integration-tests-serverless** — los tests de integración se corren
  en un stage *separado* (post-merge a main), no en el gate de PR — para
  no bloquear PRs por flakes de red.
