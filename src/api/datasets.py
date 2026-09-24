"""Registry of datasets the platform can query, each isolated in its own pair
of Postgres schemas within the same database. A request picks exactly one
dataset (never both at once) via a `dataset` field/query param that defaults
to "olist" everywhere for backward compatibility.
"""
from __future__ import annotations

from typing import Literal, TypedDict

Dataset = Literal["olist", "us"]


class DatasetInfo(TypedDict):
    label: str
    analytics_schema: str
    raw_schema: str


DATASETS: dict[Dataset, DatasetInfo] = {
    "olist": {
        "label": "Brazilian E-Commerce (Olist)",
        "analytics_schema": "analytics",
        "raw_schema": "raw",
    },
    "us": {
        "label": "US E-Commerce (synthetic, 1M orders)",
        "analytics_schema": "analytics_us",
        "raw_schema": "raw_us",
    },
}


def analytics_schema(dataset: str) -> str:
    try:
        return DATASETS[dataset]["analytics_schema"]  # type: ignore[index]
    except KeyError:
        raise ValueError(f"unknown dataset: {dataset!r}") from None


def raw_schema(dataset: str) -> str:
    try:
        return DATASETS[dataset]["raw_schema"]  # type: ignore[index]
    except KeyError:
        raise ValueError(f"unknown dataset: {dataset!r}") from None
