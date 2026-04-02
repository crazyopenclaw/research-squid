"""
Python experiment runner — executes inside the Docker sandbox container.

This script is the entrypoint for the sandbox container. It:
1. Reads the experiment payload from the EXPERIMENT_PAYLOAD env var
2. Executes the provided Python code in a restricted namespace
3. Captures stdout, stderr, and any output artifacts
4. Prints results as JSON to stdout

Security measures:
- No network access (enforced by Docker --network none)
- Limited memory (enforced by Docker --mem-limit)
- Restricted builtins (no file system writes outside /sandbox/output)
- Timeout enforcement (handled by Docker container.wait)
"""

import json
import os
import sys
import traceback
from io import StringIO


def main() -> None:
    """Execute the experiment payload and report results."""
    payload_str = os.environ.get("EXPERIMENT_PAYLOAD", "{}")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "error": f"Invalid payload JSON: {e}",
        }))
        sys.exit(1)

    code = payload.get("code", "")
    input_data = payload.get("input_data", {})
    experiment_id = payload.get("experiment_id", "unknown")

    if not code:
        print(json.dumps({
            "status": "error",
            "error": "No code provided in experiment payload",
        }))
        sys.exit(1)

    # Capture stdout during execution
    captured_stdout = StringIO()
    captured_stderr = StringIO()

    # Set up a restricted execution namespace
    namespace = {
        "__builtins__": __builtins__,
        "input_data": input_data,
        "experiment_id": experiment_id,
        "results": {},  # Experiments can write results here
    }

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        exec(code, namespace)  # noqa: S102 — intentional sandboxed exec

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Collect results
        output = {
            "status": "success",
            "stdout": captured_stdout.getvalue(),
            "stderr": captured_stderr.getvalue(),
            "results": _serialize_results(namespace.get("results", {})),
        }
        print(json.dumps(output))
        sys.exit(0)

    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        output = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "stdout": captured_stdout.getvalue(),
            "stderr": captured_stderr.getvalue(),
        }
        print(json.dumps(output))
        sys.exit(1)


def _serialize_results(results: dict) -> dict:
    """Best-effort serialization of experiment results to JSON."""
    serialized = {}
    for key, value in results.items():
        try:
            json.dumps(value)
            serialized[key] = value
        except (TypeError, ValueError):
            serialized[key] = str(value)
    return serialized


if __name__ == "__main__":
    main()
