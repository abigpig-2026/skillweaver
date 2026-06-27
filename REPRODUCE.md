# Reproduction Guide

This guide focuses on the core artifact workflows kept in the submission package.

## 1. Environment Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If you plan to synthesize new trigger skills or enable LLM-assisted I/O extraction, configure `DEEPSEEK_API_KEY` in `.env` or your shell environment.

## 2. Dependency-Loop Discovery

Run discovery on one included scenario:

```bash
python scripts/discover_cycles.py \
  --skills-dir datasets/s2-content-creation \
  --output-dir output/s2_discovery
```

Expected outputs:

- `output/s2_discovery/results.json`
- `output/s2_discovery/summary.md`
- `output/s2_discovery/udg_data.pkl`

Useful options:

- `--max-skills N` to run a smaller smoke test.
- `--use-llm-io` to enable LLM-assisted I/O extraction.
- `--eta`, `--tau-m`, `--tau-t`, `--rho` to override graph thresholds.

## 3. Trigger-Skill Synthesis

After discovery, synthesize one retained path into a trigger skill:

```bash
python scripts/synthesize_payload.py \
  --udg-data output/s2_discovery/udg_data.pkl \
  --results-file output/s2_discovery/results.json \
  --cycle-index 0 \
  --output-dir output/generated_skills
```

During synthesis, the selected loop is converted into one structured retained-path input that includes the ordered skills and compact stage metadata for each step. That single input is then used to generate `SKILL.md`.

Expected output:

- one generated skill folder under `output/generated_skills/`
- `SKILL.md`
- `payload_details.json`
- `selected_cycle.json`

## 4. Real Case Study Example

A ready-to-use trigger skill is included at:

- `examples/case_study_seo_wechat/trigger_skill/skill_003_seo-wechat-pipeline/SKILL.md`
- `examples/case_study_seo_wechat/trigger_skill/skill_003_seo-wechat-pipeline/payload_details.json`

The same case-study folder also bundles the three supporting skills under `examples/case_study_seo_wechat/supporting_skills/` so that the example can be inspected or staged without browsing the full dataset tree.

To stage the full case study into a clean workspace:

```bash
python scripts/install_case_study.py --workspace-dir C:\path\to\workspace
```

This copies the three supporting benign skills together with the trigger skill.

## 5. Optional Runtime Use

The included case-study README explains how to load the staged workspace into an agent runtime and which initial trigger phrase to send.

## 6. Smoke Checks

The following commands are safe quick checks for the artifact layout:

```bash
python scripts/discover_cycles.py --help
python scripts/synthesize_payload.py --help
python scripts/install_case_study.py --help
```
