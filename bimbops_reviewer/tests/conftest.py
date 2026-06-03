import pathlib
import sys

# review_core.py lives next to agent.py (flat layout for mlflow code_paths);
# put it on the path so the pure-core unit tests can import it directly.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "agent"))
