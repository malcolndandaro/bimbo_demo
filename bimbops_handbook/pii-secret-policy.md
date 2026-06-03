# PII & Secret Policy — Datos sensibles y credenciales

> Reglas de seguridad de BimbOps para manejo de secretos, inyección de SQL y datos
> personales (PII) en código de datos.

### [SEC-01] Prohibido secretos o credenciales en el código
- **Severity:** BLOCKER
- **Citation:** BimbOps Handbook › PII & Secret Policy › SEC-01

Tokens, passwords, client secrets, connection strings y API keys nunca van en el
código fuente ni en notebooks. Se usan Databricks Secrets (`dbutils.secrets.get`) o
Azure Key Vault. Un secreto en un repo público se considera comprometido.
❌ `TOKEN = "dapi…"` o `password="…"` en el código.
✅ `dbutils.secrets.get(scope="bimbops", key="…")`.

### [SEC-02] No construir SQL por interpolación de input externo
- **Severity:** BLOCKER
- **Citation:** BimbOps Handbook › PII & Secret Policy › SEC-02

Construir queries concatenando o interpolando input externo (args, widgets, request)
abre inyección de SQL. Se usan queries parametrizadas / binds, o validación estricta
contra una lista blanca.
❌ `query = f"SELECT * FROM t WHERE region = '{region}'"` con `region` desde `sys.argv`.
✅ Parámetros del statement execution / binds, o validar `region` contra un set permitido.

### [SEC-03] No loguear PII
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › PII & Secret Policy › SEC-03

Emails, nombres, direcciones, teléfonos y otros datos personales no se imprimen en
`print` ni en logs. Si se necesita trazabilidad, se enmascara o se usan identificadores.

### [SEC-04] Acceso a datos sensibles vía gobernanza de Unity Catalog
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › PII & Secret Policy › SEC-04

El acceso a columnas sensibles se hace mediante column masks / row filters de UC, no
copiando datos a tablas ad-hoc sin gobernanza.
