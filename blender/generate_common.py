"""Helpers shared by the asset builders."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def write_manifest(name, data):
    """Record per-asset facts the runtime wants without parsing GLBs."""
    directory = os.path.join(HERE, ".build", "manifest")
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, f"{name}.json"), "w", encoding="utf8") as handle:
        json.dump(data, handle, indent="\t")
