# SkillWeaver Artifact

This repository contains the submission artifact for `SkillWeaver`, a framework for discovering cross-skill dependency loops and synthesizing trigger skills that preserve those loops in skill-enabled agent ecosystems.

The package is organized as a reusable project rather than around paper question numbers. It includes:

- the core implementation for skill parsing, dependency-graph construction, cycle enumeration, and trigger-skill synthesis;
- the four included skill ecosystems used in the study;
- a real case-study trigger skill that can be installed directly into a clean workspace; and
- minimal scripts for discovery, synthesis, and case-study setup.

## Quick Start

```bash
pip install -r requirements.txt
```

If you want to use LLM-assisted parsing or synthesize new trigger skills, copy `.env.example` to `.env` and set `DEEPSEEK_API_KEY`.

### 1. Discover dependency loops

```bash
python scripts/discover_cycles.py \
  --skills-dir datasets/s2-content-creation \
  --output-dir output/s2_discovery
```

This produces `results.json`, `summary.md`, and `udg_data.pkl` under `output/s2_discovery/`.

### 2. Synthesize a trigger skill from a discovered loop

```bash
python scripts/synthesize_payload.py \
  --udg-data output/s2_discovery/udg_data.pkl \
  --results-file output/s2_discovery/results.json \
  --cycle-index 0 \
  --output-dir output/generated_skills
```

The synthesis stage uses one explicit LLM input: a structured retained path that lists the ordered skills in the selected loop together with compact stage metadata, including each stage's role, required inputs, produced outputs, and next hand-off target.

### 3. Use the included case study directly

A ready-to-install S2 case study is provided under `examples/case_study_seo_wechat/`.

To copy its required skills into a clean workspace directory:

```bash
python scripts/install_case_study.py --workspace-dir C:\path\to\workspace
```

The case study installs these four folders:

- `seo-keyword-researcher`
- `blog-writer`
- `wechat-publisher`
- `skill_003_seo-wechat-pipeline`

Its entry trigger is stored in `payload_details.json` and can be used as the initial prompt when the workspace is loaded by an agent runtime.

## Repository Layout

```text
SkillWeaver_submission/
|-- README.md
|-- REPRODUCE.md
|-- requirements.txt
|-- .env.example
|-- .gitignore
|
|-- modules/
|   |-- __init__.py
|   |-- skill_graph_builder.py      # skill parsing and action extraction
|   |-- multi_skill_pathfinder.py   # UDG construction and closed-loop enumeration
|   |-- illusion_payload.py         # trigger-skill synthesis from a structured retained path
|   `-- dynamic_entropy.py          # auxiliary evaluation utilities
|
|-- scripts/
|   |-- discover_cycles.py          # artifact entry point for loop discovery
|   |-- synthesize_payload.py       # artifact entry point for trigger-skill synthesis
|   `-- install_case_study.py       # install the included case study into a workspace
|
|-- datasets/
|   |-- s1-office-collaboration/
|   |-- s2-content-creation/
|   |-- s3-data-analysis/
|   `-- s4-customer-service/
|
|-- prompts/
|   |-- io_extraction_prompt.md
|   `-- payload_synthesis_prompt.md
|
|-- examples/
|   `-- case_study_seo_wechat/
|       |-- README.md
|       `-- trigger_skill/
|           `-- skill_003_seo-wechat-pipeline/
|               |-- SKILL.md
|               `-- payload_details.json
|
`-- docs/
    |-- method_notes.md
    `-- filter_design.md
```

## Included Workflows

### Discovery
`modules/skill_graph_builder.py` parses skill directories into action-level representations. `modules/multi_skill_pathfinder.py` builds the unified dependency graph and enumerates bounded closed paths.

### Synthesis
`modules/illusion_payload.py` converts a retained path into a trigger-skill folder containing `SKILL.md` and `payload_details.json`. The retained path is passed to the LLM as one structured input rather than as several separate prompt fields.

### Case Study
`examples/case_study_seo_wechat/` contains a real S2 trigger skill derived from the retained path `seo-keyword-researcher -> Blog Writer -> wechat-content-creator`.

## Notes

- The included scripts intentionally expose only the minimal artifact workflows needed to inspect the method and reproduce representative outputs.
- The repository does not ship pre-generated `output/` directories. Those are created only when you run the scripts.
- The included case-study trigger skill is a real generated artifact, not a reconstructed paper snippet.

## Ethics

This artifact is provided for authorized security research, benchmarking, and defense evaluation in controlled environments.
