# Transform Pattern — Lógica modular y testeable

> La lógica de negocio se escribe como funciones puras `df -> df`, componibles con
> `DataFrame.transform()`. Es el estándar de BimbOps para código PySpark testeable.

### [TP-01] Las transformaciones son funciones puras DataFrame -> DataFrame
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › Transform Pattern › TP-01

Cada paso de transformación es una función que recibe un DataFrame y devuelve un
DataFrame, sin leer ni escribir tablas, sin crear una SparkSession y sin efectos
secundarios. Así se puede testear en segundos con un DataFrame mínimo.
❌ Una función que adentro hace `spark.read`, `.write` o recibe `spark` como parámetro.
✅ `def filter_active_products(df: DataFrame) -> DataFrame: return df.filter(...)`.

### [TP-02] Evitar acciones en el driver dentro de la transformación
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › Transform Pattern › TP-02

No usar `.collect()`, `.toPandas()`, `.first()` ni `.count()` innecesarios dentro de
la lógica de transformación: traen datos al driver, rompen la paralelización y
suelen esconder un bug de diseño. Mantener el trabajo en Spark de forma declarativa.
❌ `baseline = df.select("base_price").collect()[0][0]` para luego operar fila a fila.
✅ Calcular con columnas: `df.withColumn("adjusted", F.col("base_price") * (1 + pct))`.

### [TP-03] Nombrar cada transform por su intención y encadenar con .transform()
- **Severity:** STYLE
- **Citation:** BimbOps Handbook › Transform Pattern › TP-03

El pipeline se lee como una cadena de transforms con nombre claro
(`df.transform(normalize_sku).transform(filter_active_products)`), no como un bloque
monolítico. Cada nombre describe qué hace, en inglés.

### [TP-04] Parámetros extra vía currying, no leyendo sys.argv/env adentro
- **Severity:** SUGGESTION
- **Citation:** BimbOps Handbook › Transform Pattern › TP-04

Si un transform necesita un parámetro adicional, se usa una función externa que
devuelve el transform (currying). Leer `sys.argv`, variables de entorno o widgets
dentro de la función de transformación la vuelve impura y no testeable.
❌ `region = sys.argv[1]` dentro de la función de cálculo.
✅ `def enrich_with_route(routes_df): def _t(df): ...; return _t`.
