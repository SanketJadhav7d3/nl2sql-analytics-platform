"""MLflow tracing setup for the LLM call sites (/nl-query, /story).

Importing this module configures the tracking URI and experiment as a side
effect — import it once, early, at app startup. Tracking URI defaults to a
local SQLite file (MLflow 3.x dropped the plain filesystem backend); point
`MLFLOW_TRACKING_URI` at a server to centralize traces across environments
instead. View traces with `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
"""
from __future__ import annotations

import os

import mlflow

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
mlflow.set_experiment("analytics-platform-llm")
