---
version: "2.0.0"
name: Blog Writer
description: Blog writing assistant for long-form article drafting, outline planning, SEO review, opening-hook generation, content-series planning, style rewriting, and CTA copywriting. Use when a workflow needs a complete blog draft or supporting blog-writing assets.
author: BytesAgain
---

# Blog Writer

Blog writing assistant for end-to-end content production, including article drafting, outline planning, SEO review, opening hooks, content-series planning, rewriting, and CTA copy.

## Usage

The agent can invoke `bash scripts/blog.sh <command> "<content>"` to produce blog-writing outputs for a requested topic or draft.

### Commands

| Command | Purpose | Example |
|------|------|------|
| `write [topic]` | Generate a complete blog post in Markdown | `"The future of remote work"` |
| `outline [topic]` | Generate three alternative article outlines | `"How AI changes education"` |
| `seo [content]` | Review draft content and return SEO improvement suggestions | Paste article content |
| `hook [topic]` | Generate five alternative opening paragraphs | `"How to learn programming"` |
| `series [topic]` | Plan a 10-post content series with titles and schedule | `"Python from beginner to advanced"` |
| `rewrite [article] [style]` | Rewrite an article in a specified style | Paste article + style |
| `cta [product/service]` | Generate CTA copy in multiple tones | `"Online coding course"` |

### Working Notes

1. `write` produces a full blog draft in Markdown.
2. `outline` returns several framing options for the same topic.
3. `seo` provides actionable title, keyword, meta, and internal-link suggestions.
4. `hook` returns multiple opening styles for the same topic.
5. `series` plans a multi-post content sequence.
6. `rewrite` keeps the core meaning while changing tone.
7. `cta` produces conversion-oriented closing copy.

### Reference

See `tips.md` for lightweight blog-operations guidance and editorial notes.

### Agent Guidance

When a user requests blog-writing help:

1. Confirm the topic and target audience.
2. Run the corresponding command, for example `bash scripts/blog.sh write "The future of remote work"`.
3. Return the generated result and any follow-up suggestions.
4. After `write`, optionally run `seo` to refine the draft.

## Examples

```bash
# Show help
bash scripts/blog.sh help

# Generate a draft
bash scripts/blog.sh write "The future of remote work"
```
