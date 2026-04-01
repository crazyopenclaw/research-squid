#!/bin/bash
set -e
echo "Starting HiveResearch Coordinator..."
uvicorn hive.coordinator.app:app --host 0.0.0.0 --port 8000
