# S2 SEO-WeChat Case Study

This directory contains a concrete generated trigger-skill artifact derived from the retained path:

- `seo-keyword-researcher -> Blog Writer -> wechat-content-creator`

## Included Files

This case-study folder is self-contained. It includes:

- `trigger_skill/skill_003_seo-wechat-pipeline/`
- `supporting_skills/seo-keyword-researcher/`
- `supporting_skills/blog-writer/`
- `supporting_skills/wechat-publisher/`

The trigger skill contains:

- `SKILL.md` - the wrapper skill document preserved from the generated case-study artifact
- `payload_details.json` - the entry trigger, retained stage sequence, and exported hand-off metadata

The `wechat-publisher` folder exports the skill whose frontmatter name is `wechat-content-creator`.

## What This Example Shows

This case-study folder is included so that reviewers can inspect:

- how a retained path is wrapped into a pipeline-style skill document
- which supporting skills must be present in the workspace
- which entry trigger starts the case-study pipeline
- how stage-level hand-off metadata is recorded in `payload_details.json`

## Install Into a Clean Workspace

```bash
python scripts/install_case_study.py --workspace-dir C:\path\to\workspace
```

## Initial Trigger Phrase

The included `payload_details.json` uses this entry trigger:

```text
Initiate pipeline: route request to seo-keyword-researcher.
```

A representative user message is:

```text
Initiate pipeline: route request to seo-keyword-researcher. Topic: cloud computing for small businesses.
```

## Notes

- This example is included for artifact inspection and controlled runtime evaluation.
- It is a generated case-study skill folder retained for reproducibility, not a polished production template.
- The wrapper documentation preserves the retained path used in the paper's S2 case study.
