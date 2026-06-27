#!/usr/bin/env python3
"""Synthesize one trigger skill from a discovered retained path."""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_local_env(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from modules.illusion_payload import DeepSeekPayloadSolver
from modules.multi_skill_pathfinder import CyclicPath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthesize a trigger skill from discovery outputs.")
    parser.add_argument("--udg-data", required=True, help="Path to udg_data.pkl from discovery.")
    parser.add_argument("--results-file", required=True, help="Path to discovery results.json.")
    parser.add_argument("--cycle-index", type=int, default=None, help="Zero-based cycle index in results.json.")
    parser.add_argument("--cycle-id", default=None, help="Cycle identifier in results.json.")
    parser.add_argument("--output-dir", required=True, help="Directory to receive the exported skill folder.")
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    return parser.parse_args()


def resolve_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_cycle(results_path: Path, cycle_index: int | None, cycle_id: str | None) -> dict:
    with results_path.open("r", encoding="utf-8") as handle:
        results = json.load(handle)

    cycles = results.get("cycles", [])
    if cycle_id is not None:
        for cycle in cycles:
            if cycle.get("cycle_id") == cycle_id:
                return cycle
        raise SystemExit(f"Cycle id not found: {cycle_id}")

    if cycle_index is None:
        raise SystemExit("Provide either --cycle-index or --cycle-id.")
    if cycle_index < 0 or cycle_index >= len(cycles):
        raise SystemExit(f"Cycle index out of range: {cycle_index}")
    return cycles[cycle_index]


def reconstruct_path(cycle: dict, udg) -> CyclicPath:
    cycle_nodes = list(cycle["cycle_nodes"])
    edges = []
    for index, source in enumerate(cycle_nodes):
        target = cycle_nodes[(index + 1) % len(cycle_nodes)]
        edge = udg.global_edges.get((source, target))
        if edge is None:
            raise SystemExit(f"Missing edge for retained path transition: {source} -> {target}")
        edges.append(edge)

    skill_names = [udg.global_action_nodes[node_id].parent_skill_name for node_id in cycle_nodes]
    return CyclicPath(
        path_action_ids=cycle_nodes,
        path_skill_ids=list(cycle["skill_sequence"]),
        path_skill_names=skill_names,
        path_edges=edges,
        hop_count=int(cycle["hop_count"]),
        total_affinity=float(cycle["total_affinity"]),
        avg_semantic_sim=float(cycle["avg_semantic_sim"]),
    )


def main() -> None:
    args = parse_args()
    udg_data_path = resolve_repo_path(args.udg_data)
    results_path = resolve_repo_path(args.results_file)
    output_dir = resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with udg_data_path.open("rb") as handle:
        udg_data = pickle.load(handle)
    udg = udg_data["udg"]

    cycle = load_cycle(results_path, args.cycle_index, args.cycle_id)
    path = reconstruct_path(cycle, udg)

    solver = DeepSeekPayloadSolver(model=args.model)
    solver.set_udg(udg)
    artifact = solver.synthesize_payload_for_path(path, udg.global_action_nodes)
    exported = solver.export_payload(artifact, str(output_dir))

    if exported is None:
        raise SystemExit("Payload synthesis completed without an exported folder.")

    with (Path(exported) / "selected_cycle.json").open("w", encoding="utf-8") as handle:
        json.dump(cycle, handle, indent=2, ensure_ascii=False)

    print(f"[OK] Exported trigger skill to: {exported}")


if __name__ == "__main__":
    main()
