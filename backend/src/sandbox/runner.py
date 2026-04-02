"""
Docker sandbox runner — executes experiments in isolated containers.

Each experiment runs in a fresh Docker container with:
  - No network access (--network none)
  - Memory limits (256MB default)
  - CPU limits (0.5 cores)
  - Timeout enforcement
  - Pre-installed scientific libraries only

The runner communicates with experiments via stdin (JSON spec in)
and stdout/stderr (results out).
"""

import json
import time
from typing import Any

try:
    import docker
    from docker.errors import ImageNotFound
    _HAS_DOCKER = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    docker = None
    ImageNotFound = RuntimeError
    _HAS_DOCKER = False

from src.config import Settings, settings as default_settings
from src.events.bus import EventBus
from src.models.events import Event, EventType


class SandboxRunner:
    """
    Dispatches ExperimentSpecs to Docker containers for execution.

    Each experiment runs in a fresh, isolated container. The runner:
    1. Builds the experiment payload (code + input data)
    2. Creates a container from the sandbox image
    3. Passes the payload via environment variable
    4. Waits for completion (with timeout)
    5. Captures stdout, stderr, and exit code
    6. Cleans up the container

    Usage:
        runner = SandboxRunner(settings)
        result = await runner.run_experiment(exp_id, exp_data)
    """

    def __init__(
        self,
        config: Settings | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config or default_settings
        self._bus = event_bus
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Lazily initialize the Docker client."""
        if not _HAS_DOCKER:
            raise RuntimeError(
                "The optional 'docker' Python package is not installed. "
                "Install backend sandbox dependencies to enable experiment "
                "execution."
            )
        if not self._client:
            self._client = docker.from_env()
        return self._client

    async def run_experiment(
        self,
        experiment_id: str,
        experiment_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute an experiment in a Docker sandbox.

        Args:
            experiment_id: Unique ID of the experiment.
            experiment_data: Dict with experiment properties from Neo4j.

        Returns:
            Dict with stdout, stderr, exit_code, and execution_time.
        """
        client = self._get_client()

        # Extract experiment spec
        code = experiment_data.get("spec_code", "")
        input_data = self._extract_input_data(experiment_data)
        timeout = min(
            experiment_data.get("spec_timeout", self._config.sandbox_timeout),
            self._config.sandbox_timeout_hard_cap,
        )

        # Build payload for the sandbox runner script
        payload = json.dumps({
            "experiment_id": experiment_id,
            "code": code,
            "input_data": input_data,
        })

        start_time = time.time()

        try:
            # Run in a fresh container
            container = client.containers.run(
                image=self._config.sandbox_image,
                command=None,  # Uses entrypoint from Dockerfile
                environment={"EXPERIMENT_PAYLOAD": payload},
                network_mode=self._config.sandbox_network,
                mem_limit=self._config.sandbox_memory_limit,
                cpu_period=self._config.sandbox_cpu_period,
                cpu_quota=self._config.sandbox_cpu_quota,
                detach=True,
                remove=False,  # We need to read logs before removing
            )

            # Wait for completion with timeout
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)

            # Capture output
            raw_stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            raw_stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )
            parsed_output = self._parse_runner_output(raw_stdout)

            # Clean up
            container.remove(force=True)

            execution_time = time.time() - start_time

            return {
                "stdout": parsed_output["stdout"][: self._config.sandbox_stdout_cap],
                "stderr": (
                    parsed_output["stderr"] or raw_stderr
                )[: self._config.sandbox_stderr_cap],
                "exit_code": exit_code,
                "execution_time": execution_time,
                "artifacts": parsed_output["artifacts"],
                "raw_stdout": raw_stdout[: self._config.sandbox_stdout_cap],
                "raw_stderr": raw_stderr[: self._config.sandbox_stderr_cap],
            }

        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "stdout": "",
                "stderr": f"Sandbox error: {str(e)}",
                "exit_code": -1,
                "execution_time": execution_time,
                "artifacts": {},
                "raw_stdout": "",
                "raw_stderr": f"Sandbox error: {str(e)}",
            }

    async def ensure_image_exists(self) -> bool:
        """
        Check if the sandbox Docker image exists, build if not.

        Returns True if the image is available.
        """
        client = self._get_client()
        try:
            client.images.get(self._config.sandbox_image)
            return True
        except ImageNotFound:
            return False

    @staticmethod
    def _extract_input_data(experiment_data: dict[str, Any]) -> dict[str, Any]:
        raw = experiment_data.get(
            "spec_input_data",
            experiment_data.get("input_data", {}),
        )
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _parse_runner_output(raw_stdout: str) -> dict[str, Any]:
        text = raw_stdout.strip()
        if not text:
            return {"stdout": "", "stderr": "", "artifacts": {}}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"stdout": text, "stderr": "", "artifacts": {}}
        if not isinstance(payload, dict):
            return {"stdout": text, "stderr": "", "artifacts": {}}
        return {
            "stdout": str(payload.get("stdout", "")),
            "stderr": str(payload.get("stderr", "")),
            "artifacts": payload.get("results", {}) or {},
        }
