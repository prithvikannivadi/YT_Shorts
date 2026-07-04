"""Load config.yaml and expose it as nested attribute access."""
from __future__ import annotations

from pathlib import Path

import yaml


class Cfg(dict):
    def __getattr__(self, name):
        try:
            v = self[name]
        except KeyError as e:
            raise AttributeError(name) from e
        if isinstance(v, dict):
            return Cfg(v)
        return v


def load_config(path: str | Path = "config.yaml") -> Cfg:
    with open(path, "r", encoding="utf-8") as f:
        return Cfg(yaml.safe_load(f))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
