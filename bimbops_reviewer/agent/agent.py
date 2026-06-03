"""Minimal BimbOps Reviewer — slice 03 tracer bullet.

Returns one canned finding regardless of input. Its only job is to prove the
GitHub Actions ↔ Databricks Model Serving ↔ PR-comment wiring end to end.
Real retrieval-grounded review (Vector Search over the BimbOps Handbook,
structured findings, severity) arrives in slice 04.
"""

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

_CANNED = (
    "🤖 **BimbOps Reviewer (tracer bullet)**\n\n"
    "✅ La conexión CI → Databricks Model Serving → comentario de PR funciona "
    "de extremo a extremo.\n\n"
    "Este es un hallazgo de ejemplo (_canned_); la revisión real contra el "
    "BimbOps Handbook (hallazgos citados, severidad) llega en la slice 04."
)


class BimbopsReviewerTracer(ResponsesAgent):
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=_CANNED, id="msg_tracer_1")]
        )


mlflow.models.set_model(BimbopsReviewerTracer())
