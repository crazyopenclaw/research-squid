"""Backend registry — maps backend_type string to backend class."""

REGISTRY = {
    "sandbox_python": "hive.backends.sandbox_python.executor:SandboxPythonBackend",
    "gpu_training": "hive.backends.gpu_training.executor:GPUTrainingBackend",
    "bio_pipeline": "hive.backends.bio_pipeline.executor:BioBackend",
    "simulation": "hive.backends.simulation.executor:SimulationBackend",
}
