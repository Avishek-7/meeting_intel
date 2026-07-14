#!/usr/bin/env python3
"""Normalize graphify extraction files to satisfy required schema fields.

This script patches missing `source_file` metadata on nodes and edges.
It is idempotent and safe to run multiple times.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("graphify-out/.graphify_extract.json")


def _normalize_node(node: dict[str, Any], fallback_source: str) -> bool:
    changed = False

    if "source_file" not in node:
        if "source" in node and isinstance(node["source"], str):
            node["source_file"] = node.pop("source")
        else:
            node["source_file"] = fallback_source
        changed = True

    if "file_type" not in node or not isinstance(node.get("file_type"), str):
        node["file_type"] = "document"
        changed = True

    return changed


def _normalize_edge(
    edge: dict[str, Any],
    fallback_source: str,
    node_source_map: dict[str, str],
) -> bool:
    changed = False

    if "source_file" not in edge:
        source_id = edge.get("source")
        inferred = node_source_map.get(source_id, fallback_source)
        edge["source_file"] = inferred
        changed = True

    return changed


def normalize_extraction(path: Path, fallback_source: str = "semantic://normalized") -> tuple[int, int]:
    payload = json.loads(path.read_text())

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Extraction JSON must contain list fields: nodes and edges")

    changed_nodes = 0
    changed_edges = 0

    node_source_map: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if _normalize_node(node, fallback_source):
            changed_nodes += 1
        node_id = node.get("id")
        source_file = node.get("source_file")
        if isinstance(node_id, str) and isinstance(source_file, str):
            node_source_map[node_id] = source_file

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if _normalize_edge(edge, fallback_source, node_source_map):
            changed_edges += 1

    path.write_text(json.dumps(payload, indent=2))
    return changed_nodes, changed_edges


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize graphify extraction schema")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to extraction JSON (default: graphify-out/.graphify_extract.json)",
    )
    parser.add_argument(
        "--fallback-source",
        default="semantic://normalized",
        help="Fallback source_file value when metadata is missing",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    changed_nodes, changed_edges = normalize_extraction(args.input, args.fallback_source)
    print(
        f"Normalized {args.input}: changed_nodes={changed_nodes}, changed_edges={changed_edges}"
    )


if __name__ == "__main__":
    main()
