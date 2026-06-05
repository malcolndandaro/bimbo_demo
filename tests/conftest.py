"""Fixtures for serverless integration tests (slice 07).

`spark` is a Databricks Connect serverless session against the real workspace —
no local cluster, billed per second. Tables live in bimbo.<schema> (already
seeded). databricks-connect is imported lazily so plain collection (without it
installed) doesn't error.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

# Import the vendored transforms (src/bakery) without the old external sys.path hack.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

TEST_CATALOG = os.environ.get("BIMBO_TEST_CATALOG", "bimbo")
TEST_SCHEMA = os.environ.get("BIMBO_TEST_SCHEMA", "dev")


@pytest.fixture(scope="session")
def spark():
    from databricks.connect import DatabricksSession  # lazy: only when tests actually run

    return DatabricksSession.builder.serverless(True).getOrCreate()


@pytest.fixture
def fqn():
    def _fqn(table: str) -> str:
        return f"{TEST_CATALOG}.{TEST_SCHEMA}.{table}"

    return _fqn
