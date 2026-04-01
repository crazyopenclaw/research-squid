"""Routes ExperimentSpec to correct backend."""

import importlib
from typing import Dict, Optional, Type

from hive.backends.base import BaseBackend


REGISTRY: Dict[str, str] = {
    "sandbox_python": "hive.backends.sandbox_python.executor:SandboxPythonBackend",
    "gpu_training": "hive.backends.gpu_training.executor:GPUTrainingBackend",
    "bio_pipeline": "hive.backends.bio_pipeline.executor:BioBackend",
    "simulation": "hive.backends.simulation.executor:SimulationBackend",
}


def get_backend(backend_type: str) -> Optional[BaseBackend]:
    """Load and instantiate a backend by type string."""
    module_path = REGISTRY.get(backend_type)
    if not module_path:
        return None

    module_name, class_name = module_path.rsplit(":", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls()
