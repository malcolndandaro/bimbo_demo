# SQL Conventions — Estilo SQL (dialect=databricks)

> Convenciones de SQL de BimbOps, alineadas con la configuración de sqlfluff del
> repo. El linter cubre el estilo; estas reglas explican el porqué y el agente las cita.

### [SQL-01] Keywords en UPPERCASE, identificadores en lowercase
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › SQL Conventions › SQL-01

Palabras clave (`SELECT`, `FROM`, `GROUP BY`) en mayúsculas; tablas y columnas en
`lowercase`. Mezclar (`Route_Name`, `BASE_PRICE`) rompe la consistencia y los diffs.

### [SQL-02] Alias explícitos con AS; no ordenar por ordinal
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › SQL Conventions › SQL-02

Toda columna derivada lleva alias con `AS`. No se usa `ORDER BY 3` ni `GROUP BY 1,2`
por posición: se nombran las columnas para que el query sobreviva a cambios de orden.
❌ `sum(adjusted_price) total_adjusted … order by 3`.
✅ `SUM(adjusted_price) AS total_adjusted … ORDER BY total_adjusted DESC`.

### [SQL-03] Columnas explícitas en vistas productivas (no SELECT *)
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › SQL Conventions › SQL-03

Las vistas y tablas gold listan columnas explícitamente. `SELECT *` acopla la vista
al esquema upstream y filtra columnas nuevas sin control.

### [SQL-04] Un identificador por línea en SELECT largos
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › SQL Conventions › SQL-04

En SELECT con varias columnas, una por línea y sangría consistente para diffs limpios.
