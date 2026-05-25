# `bad-pr/` — Anti-ejemplos intencionales

Estos archivos son **inválidos a propósito** para demostrar lo que el
quality gate detecta. Durante la demo, los corremos directamente contra
los linters y mostramos los tres failures.

| Archivo / carpeta | Herramienta que lo rechaza | Tipo de violaciones |
|---|---|---|
| `bad_python.py` | Ruff | imports no usados/desorden, mutable defaults, bare except, `== None`, SQL injection (`%`), `assert False` |
| `bad_sql.sql` | sqlfluff (dialect=databricks) | keywords en minúscula, identifiers mezclando case, aliases sin `AS`, ORDER BY por posición, espaciado inconsistente |
| `broken_bundle/databricks.yml` | `databricks bundle validate` | referencia a variable inexistente (`${var.catalogo}` typo) |

## Cómo correr la demo localmente

```bash
# desde 04-ci-quality-gate/

# 1) Estado verde — lo que vive en el repo real
ruff check src/                          # → All checks passed!
sqlfluff lint sql/                       # → All Finished!
databricks bundle validate -t dev        # → Validation OK!

# 2) Estado rojo — lo que el quality gate bloquea
ruff check bad-pr/bad_python.py          # → 13 errors
sqlfluff lint bad-pr/bad_sql.sql         # → muchos errores CP01/CP02/CP03/LT01
(cd bad-pr/broken_bundle && databricks bundle validate -t dev)
                                          # → Error: reference does not exist: ${var.catalogo}
```

## Estado en el repo real

Estos archivos **están excluidos** del lint normal:

- `pyproject.toml` → `[tool.ruff] exclude = ["bad-pr"]`
- `.sqlfluff` no lintea `bad-pr/` porque corremos `sqlfluff lint sql/` (path explícito)
- El `databricks.yml` raíz no incluye `bad-pr/` (es un bundle separado)

Esto evita que el repo real se vea rojo todo el tiempo.

## En GitHub Actions

`.github/workflows/pr-checks.yml` corre los 3 linters sobre los paths
limpios. Si un dev intenta commitear `bad-pr/*` al `src/`, los checks lo
detectan y bloquean el merge — exactamente el comportamiento que falta hoy
en BimbOps (F01 del assessment).
