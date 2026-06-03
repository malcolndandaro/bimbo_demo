"""Deploy the BimbOps Reviewer to a Model Serving endpoint.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/deploy_agent.py [VERSION]
First deploy creates the `bimbops-reviewer` endpoint (~15 min); a new model version
deploys in place (~minutes — the "config-only redeploy"). VERSION (argv or
$BIMBOPS_DEPLOY_VERSION) pins a specific UC model version; empty = the @prod alias.
The DABs `agent_model_version` variable feeds this for a bundle-driven version bump.
"""

from __future__ import annotations

import os
import sys

import mlflow
from databricks import agents
from mlflow.tracking import MlflowClient

FULL_NAME = "bimbo_demo.dev.bimbops_reviewer"
ENDPOINT = "bimbops-reviewer"

mlflow.set_tracking_uri("databricks")  # agents.deploy resolves the logged model via tracking
mlflow.set_registry_uri("databricks-uc")

client = MlflowClient(registry_uri="databricks-uc")
_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIMBOPS_DEPLOY_VERSION", "")
version = _arg.strip() or client.get_model_version_by_alias(FULL_NAME, "prod").version
print(f"deploying {FULL_NAME} v{version} → endpoint {ENDPOINT}…")

deployment = agents.deploy(
    FULL_NAME,
    version,
    endpoint_name=ENDPOINT,
    tags={"project": "bimbops-session2"},
)
print("endpoint_name:", deployment.endpoint_name)
print("query_endpoint:", deployment.query_endpoint)
