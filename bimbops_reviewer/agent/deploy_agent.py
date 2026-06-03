"""Deploy the BimbOps Reviewer @prod to a Model Serving endpoint.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/deploy_agent.py
Blocks ~15 min on first deploy (creates the `bimbops-reviewer` endpoint). A new
model version deploys in place — no recreation.
"""

from __future__ import annotations

import mlflow
from databricks import agents
from mlflow.tracking import MlflowClient

FULL_NAME = "bimbo_demo.dev.bimbops_reviewer"
ENDPOINT = "bimbops-reviewer"

mlflow.set_tracking_uri("databricks")  # agents.deploy resolves the logged model via tracking
mlflow.set_registry_uri("databricks-uc")

client = MlflowClient(registry_uri="databricks-uc")
version = client.get_model_version_by_alias(FULL_NAME, "prod").version
print(f"deploying {FULL_NAME} v{version} → endpoint {ENDPOINT} (≈15 min)…")

deployment = agents.deploy(
    FULL_NAME,
    version,
    endpoint_name=ENDPOINT,
    tags={"project": "bimbops-session2"},
)
print("endpoint_name:", deployment.endpoint_name)
print("query_endpoint:", deployment.query_endpoint)
