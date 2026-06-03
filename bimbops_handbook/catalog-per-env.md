# Catalog-per-Env — Aislamiento de ambientes

> Cada ambiente (dev / qa / prod) vive en su propio catálogo o esquema. El código
> nunca debe cruzar ambientes ni hardcodear nombres de catálogo.

### [ENV-01] Prohibido referenciar catálogos de otro ambiente
- **Severity:** BLOCKER
- **Citation:** BimbOps Handbook › Catalog-per-Env › ENV-01

Un job que corre en `dev` o `qa` nunca debe leer ni escribir un catálogo o esquema
de `prod` (p.ej. `bimbo_prd`, `*_prd`, `*.prod`). Cruzar ambientes rompe el
aislamiento, expone datos productivos y hace que los tests contaminen prod.
❌ `spark.table("bimbo_prd.gold_pricing")` dentro de un job de dev.
❌ `f"SELECT * FROM bimbo_prd.gold_pricing"` en código que se despliega a dev/qa.
✅ Referenciar el catálogo del ambiente actual vía variable: `{catalog}.gold_pricing`.

### [ENV-02] Parametrizar el catálogo y el esquema con variables de DABs
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › Catalog-per-Env › ENV-02

El nombre del catálogo/esquema no se hardcodea: se inyecta como `${var.catalog}` /
`${var.schema}` desde el target de DABs, o como job parameter. Así el mismo código
corre en los tres ambientes sin editar una línea.
❌ Literal `"bimbo_demo.dev"` repetido en el código.
✅ `dbutils.widgets.get("catalog")` o `${var.catalog}` resuelto por el bundle.

### [ENV-03] No hardcodear URLs de workspace ni IDs de cluster
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › Catalog-per-Env › ENV-03

Hosts de workspace, cluster ids y warehouse ids dependen del ambiente y deben venir
de variables del bundle/target, nunca incrustados en el código fuente.
