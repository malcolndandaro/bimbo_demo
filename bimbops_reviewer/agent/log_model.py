"""Log + register the BimbOps Reviewer (tracer) to Unity Catalog.

Run:  DATABRICKS_AUTH_STORAGE=plaintext python bimbops_reviewer/agent/log_model.py
Registers `bimbo_demo.dev.bimbops_reviewer` and moves the @prod alias to the new
version. Validates the model loads + predicts locally before it's deployed.
"""

from __future__ import annotations

import pathlib

import mlflow
from mlflow.tracking import MlflowClient

FULL_NAME = "bimbo_demo.dev.bimbops_reviewer"
EXPERIMENT = "/Users/malcoln.dandaro@databricks.com/bimbops_reviewer/experiment"
AGENT_FILE = str(pathlib.Path(__file__).with_name("agent.py"))

mlflow.set_tracking_uri("databricks")  # log to the workspace, not local ./mlruns
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)

with mlflow.start_run(run_name="tracer"):
    info = mlflow.pyfunc.log_model(
        name="agent",
        python_model=AGENT_FILE,  # "models from code" — agent.py calls set_model()
        input_example={"input": [{"role": "user", "content": "ping"}]},
        pip_requirements=["mlflow==3.12.0", "pydantic>=2"],
        registered_model_name=FULL_NAME,
    )
print("model_uri:", info.model_uri)

# Pre-deploy validation: load + predict in the current env (catches code errors
# before the ~15-min endpoint deploy).
mlflow.models.predict(
    model_uri=info.model_uri,
    input_data={"input": [{"role": "user", "content": "ping"}]},
    env_manager="local",
)

client = MlflowClient(registry_uri="databricks-uc")
version = max(
    client.search_model_versions(f"name='{FULL_NAME}'"), key=lambda v: int(v.version)
).version
client.set_registered_model_alias(FULL_NAME, "prod", version)
print("registered version:", version, "→ alias @prod")
