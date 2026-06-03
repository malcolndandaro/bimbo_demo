# DABs Conventions — Despliegue como código

> Convenciones de BimbOps para Databricks Asset Bundles (DABs).

### [DAB-01] Todo recurso se declara en DABs
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › DABs Conventions › DAB-01

Jobs, pipelines, dashboards y serving endpoints se definen en el bundle, no se crean
a mano en el workspace. Lo que no está en el bundle no existe para CI/CD.

### [DAB-02] Un target por ambiente; run_as SP en qa/prd
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › DABs Conventions › DAB-02

Targets `dev`, `qa`, `prd` con su `mode` (development/production). En qa y prd el
`run_as` es el Service Principal del proyecto, no un usuario humano.

### [DAB-03] bundle validate verde antes de merge
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › DABs Conventions › DAB-03

`databricks bundle validate` debe pasar para cada target como parte del quality gate
de cada PR.
