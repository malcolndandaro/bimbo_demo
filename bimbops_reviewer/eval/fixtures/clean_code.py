# Eval fixture (CLEAN): composable, pure df -> df transforms, no cross-env refs, no
# driver actions. The reviewer must emit ZERO findings (no false positives). Not deployed.
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def filter_active(df: DataFrame) -> DataFrame:
    return df.filter(F.col("is_active"))


def add_net_amount(df: DataFrame) -> DataFrame:
    return df.withColumn("net_amount", F.col("amount") - F.col("returns"))
