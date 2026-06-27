# Method Notes

This directory keeps one short implementation note for the submission artifact.

## Discovery Pipeline

1. `modules/skill_graph_builder.py` parses each skill folder into action-level nodes.
2. `modules/multi_skill_pathfinder.py` builds the unified dependency graph and enumerates bounded simple cycles.
3. `modules/illusion_payload.py` converts a retained path into a trigger-skill folder with `SKILL.md` and `payload_details.json`.

## Included Entry Points

- `scripts/discover_cycles.py`: parse one skill ecosystem and export retained paths.
- `scripts/synthesize_payload.py`: synthesize one trigger skill from a retained path.
- `scripts/install_case_study.py`: stage the included S2 case study into a clean workspace.

## Prompt Interface

The payload synthesizer exposes one explicit prompt input: a structured retained path. This input keeps the ordered skill sequence together with per-stage role, input, output, and next-target metadata, so the paper and artifact can describe the interface as single-input without reducing it to only a skill-name chain.

## Scope

The submission package keeps the core method, one real case-study example, and the minimal scripts needed to inspect or rerun representative workflows. Internal research-only experiment scaffolding is intentionally omitted here.
