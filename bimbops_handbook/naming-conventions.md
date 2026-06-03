# Naming Conventions — Nombres de recursos y código

> Convenciones de nombres de BimbOps para tablas, código y service principals.

### [NM-01] Tablas en snake_case con prefijo de capa
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › Naming Conventions › NM-01

Tablas y vistas en `snake_case`, con la capa explícita (`bronze_`, `silver_`,
`gold_`) o por esquema de capa. Ej. `gold_pricing`, `fact_sales`, `dim_product`.

### [NM-02] Funciones y variables en snake_case y descriptivas
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › Naming Conventions › NM-02

`snake_case` para funciones y variables; nombres que describen intención. Evitar
nombres de un solo carácter salvo índices de loop.

### [NM-03] Identificadores en inglés; comentarios y PR en español
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › Naming Conventions › NM-03

Nombres de código (funciones, columnas, variables) en inglés para consistencia; los
comentarios, descripciones de PR y documentación del equipo van en español.

### [NM-04] Service Principals: sp-<area>-<proyecto>-<env>
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › Naming Conventions › NM-04

Los SP siguen `sp-<area>-<proyecto>-<env>`, p.ej. `sp-bimbops-bakery-prd`. Un SP por
proyecto y ambiente, alineado con la política de identidad de BimbOps.
