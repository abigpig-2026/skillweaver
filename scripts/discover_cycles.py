#!/usr/bin/env python3
"""Discover cross-skill dependency loops from a skill directory."""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List

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

from modules.skill_graph_builder import SkillGraphBuilder
from modules.multi_skill_pathfinder import MultiSkillPathfinder, UDGBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover cross-skill dependency loops.")
    parser.add_argument("--skills-dir", required=True, help="Directory containing skill folders.")
    parser.add_argument("--output-dir", required=True, help="Directory for discovery outputs.")
    parser.add_argument("--max-skills", type=int, default=None, help="Optional limit for smoke testing.")
    parser.add_argument("--min-hop", type=int, default=3)
    parser.add_argument("--max-hop", type=int, default=6)
    parser.add_argument("--min-unique-skills", type=int, default=2)
    parser.add_argument("--max-unique-skills", type=int, default=4)
    parser.add_argument("--tau-m", type=float, default=0.3)
    parser.add_argument("--tau-t", type=float, default=0.3)
    parser.add_argument("--rho", type=float, default=0.3)
    parser.add_argument("--eta", type=float, default=0.44)
    parser.add_argument("--use-llm-io", action="store_true", help="Enable LLM-assisted I/O extraction.")
    parser.add_argument("--llm-model", default="deepseek-chat")
    return parser.parse_args()


def resolve_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (ROOT / path).resolve()


def deduplicate_cycles(cycles: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for cycle in cycles:
        key = (cycle["hop_count"], frozenset(cycle["cycle_nodes"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(cycle)
    return unique


def build_cycle_records(paths, min_hop: int, max_hop: int, min_unique: int, max_unique: int) -> List[Dict]:
    cycles = []
    for path in paths:
        unique_skills = sorted(set(path.path_skill_ids))
        unique_count = len(unique_skills)
        if path.hop_count < min_hop or path.hop_count > max_hop:
            continue
        if unique_count < min_unique or unique_count > max_unique:
            continue
        cycles.append(
            {
                "cycle_id": f"cycle_{len(cycles)}",
                "skill_sequence": list(path.path_skill_ids),
                "skill_names": list(path.path_skill_names),
                "unique_skill_count": unique_count,
                "hop_count": path.hop_count,
                "total_affinity": path.total_affinity,
                "avg_semantic_sim": path.avg_semantic_sim,
                "cycle_nodes": list(path.path_action_ids),
                "unique_skills": unique_skills,
            }
        )
    return deduplicate_cycles(cycles)


def write_summary(summary_path: Path, results: Dict) -> None:
    config = results["config"]
    stats = results["statistics"]
    cycles = results["cycles"]
    distribution = Counter((c["unique_skill_count"], c["hop_count"]) for c in cycles)

    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write("# Discovery Summary\n\n")
        handle.write("## Configuration\n")
        handle.write(f"- Skill directory: `{config['skills_dir']}`\n")
        handle.write(f"- Parsed skills: {config['skill_count']}\n")
        handle.write(f"- Action nodes: {config['action_count']}\n")
        handle.write(f"- Graph edges: {config['edge_count']}\n")
        handle.write(f"- Thresholds: tau_m={config['tau_m']}, tau_t={config['tau_t']}, rho={config['rho']}, eta={config['eta']}\n")
        handle.write(f"- LLM-assisted I/O extraction: {config['use_llm_io']}\n\n")
        handle.write("## Results\n")
        handle.write(f"- Retained cycles: {stats['total_cycles']}\n")
        handle.write(f"- Participating skills: {stats['skills_in_cycles']}\n")
        handle.write(f"- Elapsed time (s): {results['total_time_seconds']:.2f}\n\n")
        handle.write("## Distribution\n\n")
        handle.write("| Unique skills | Hop=3 | Hop=4 | Hop=5 | Hop=6 | Total |\n")
        handle.write("|---:|---:|---:|---:|---:|---:|\n")
        for unique_count in range(config["min_unique_skills"], config["max_unique_skills"] + 1):
            row = [distribution[(unique_count, hop)] for hop in range(config["min_hop"], config["max_hop"] + 1)]
            handle.write(f"| {unique_count} | " + " | ".join(str(x) for x in row) + f" | {sum(row)} |\n")


def main() -> None:
    args = parse_args()
    skills_dir = resolve_repo_path(args.skills_dir)
    output_dir = resolve_repo_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    builder = SkillGraphBuilder(use_llm_io_extraction=args.use_llm_io, model=args.llm_model)
    parsed_nodes = builder.parse_skill_directory(str(skills_dir), max_skills=args.max_skills)
    node_map = {node.skill_id: node for node in parsed_nodes}

    udg = UDGBuilder(tau_m=args.tau_m, tau_t=args.tau_t, rho=args.rho, eta=args.eta)
    udg.skill_nodes = node_map
    udg.build_skill_subgraphs()
    udg.match_all_skill_pairs()

    pathfinder = MultiSkillPathfinder(udg, min_hop=args.min_hop)
    paths = pathfinder.find_vulnerable_paths()
    cycles = build_cycle_records(paths, args.min_hop, args.max_hop, args.min_unique_skills, args.max_unique_skills)
    skills_in_cycles = sorted({skill for cycle in cycles for skill in cycle["unique_skills"]})

    results = {
        "config": {
            "skills_dir": str(skills_dir),
            "skill_count": len(parsed_nodes),
            "action_count": len(udg.global_action_nodes),
            "edge_count": len(udg.global_edges),
            "min_hop": args.min_hop,
            "max_hop": args.max_hop,
            "min_unique_skills": args.min_unique_skills,
            "max_unique_skills": args.max_unique_skills,
            "tau_m": args.tau_m,
            "tau_t": args.tau_t,
            "rho": args.rho,
            "eta": args.eta,
            "use_llm_io": args.use_llm_io,
            "llm_model": args.llm_model if args.use_llm_io else None,
        },
        "statistics": {
            "skills_in_cycles": len(skills_in_cycles),
            "total_cycles": len(cycles),
        },
        "cycles": cycles,
        "total_time_seconds": time.time() - start,
    }

    results_path = output_dir / "results.json"
    with results_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False)

    with (output_dir / "udg_data.pkl").open("wb") as handle:
        pickle.dump({"udg": udg, "skill_nodes": node_map, "config": results["config"]}, handle)

    write_summary(output_dir / "summary.md", results)
    print(f"[OK] Parsed skills: {len(parsed_nodes)}")
    print(f"[OK] Graph edges: {len(udg.global_edges)}")
    print(f"[OK] Retained cycles: {len(cycles)}")
    print(f"[OK] Results written to: {results_path}")


if __name__ == "__main__":
    main()
