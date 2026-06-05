"""Deploy the BimbOps Reviewer to a Model Serving endpoint.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/deploy_agent.py [VERSION]
First deploy creates the `bimbops-reviewer` endpoint (~15 min); a new model version
deploys in place (~minutes — the "config-only redeploy"). VERSION (argv or
$BIMBOPS_DEPLOY_VERSION): a numeric token pins that UC model version; anything else
("@prod", "prod", empty) resolves the @prod alias. The DABs `agent_model_version`
variable feeds this for a bundle-driven version bump.
"""

from __future__ import annotations

import os
import sys

import mlflow
from databricks import agents
from mlflow.tracking import MlflowClient

FULL_NAME = "bimbo.dev.bimbops_reviewer"
ENDPOINT = "bimbops-reviewer"

mlflow.set_tracking_uri("databricks")  # agents.deploy resolves the logged model via tracking
mlflow.set_registry_uri("databricks-uc")

client = MlflowClient(registry_uri="databricks-uc")
_arg = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIMBOPS_DEPLOY_VERSION", "")).strip()
# A numeric token pins that UC version; anything else ("@prod"/"prod"/"") resolves the
# @prod alias. The DABs job passes "@prod" (non-empty on purpose: an empty bundle var
# serializes to a null Terraform list element → provider panic "parameters[<nil>]...").
version = _arg if _arg.isdigit() else client.get_model_version_by_alias(FULL_NAME, "prod").version
print(f"deploying {FULL_NAME} v{version} → endpoint {ENDPOINT}…")

deployment = agents.deploy(
    FULL_NAME,
    version,
    endpoint_name=ENDPOINT,
    tags={"project": "bimbops-session2"},
)
print("endpoint_name:", deployment.endpoint_name)
print("query_endpoint:", deployment.query_endpoint)
