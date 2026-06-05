"""Log + register the BimbOps Reviewer (tracer) to Unity Catalog.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/log_model.py
Registers `bimbo.dev.bimbops_reviewer` and moves the @prod alias to the new
version. Validates the model loads + predicts locally before it's deployed.
"""

from __future__ import annotations

import pathlib

import mlflow
from mlflow.models.resources import (
    DatabricksServingEndpoint,
    DatabricksVectorSearchIndex,
)
from mlflow.tracking import MlflowClient

FULL_NAME = "bimbo.dev.bimbops_reviewer"
EXPERIMENT = "/Users/malcoln.dandaro@databricks.com/bimbops_reviewer/experiment"
AGENT_FILE = str(pathlib.Path(__file__).with_name("agent.py"))
CORE_FILE = str(pathlib.Path(__file__).with_name("review_core.py"))
LLM_ENDPOINT = "databricks-claude-opus-4-8"
VS_INDEX = "bimbo.dev.bimbops_handbook_rules_idx"

mlflow.set_tracking_uri("databricks")  # log to the workspace, not local ./mlruns
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)

# A tiny diff so the input-example validation exercises the real path (retrieval + LLM).
_EXAMPLE = {
    "input": [
        {
            "role": "user",
            "content": "diff --git a/x.py b/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+x = 1\n",
        }
    ]
}

with mlflow.start_run(run_name="grounded"):
    info = mlflow.pyfunc.log_model(
        name="agent",
        python_model=AGENT_FILE,  # "models from code" — agent.py calls set_model()
        code_paths=[CORE_FILE],  # pure cores travel with the model
        input_example=_EXAMPLE,
        pip_requirements=["mlflow==3.12.0", "databricks-sdk", "pydantic>=2"],
        resources=[  # passthrough auth for the deployed endpoint — DO NOT skip
            DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT),
            DatabricksVectorSearchIndex(index_name=VS_INDEX),
        ],
        registered_model_name=FULL_NAME,
    )
print("model_uri:", info.model_uri)

# Pre-deploy validation: load + predict in the current env (catches code errors
# before the ~15-min endpoint deploy).
mlflow.models.predict(
    model_uri=info.model_uri,
    input_data=_EXAMPLE,
    env_manager="local",
)

client = MlflowClient(registry_uri="databricks-uc")
version = max(
    client.search_model_versions(f"name='{FULL_NAME}'"), key=lambda v: int(v.version)
).version
client.set_registered_model_alias(FULL_NAME, "prod", version)
print("registered version:", version, "→ alias @prod")
