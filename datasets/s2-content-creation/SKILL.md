---
name: scene2-content-creation
description: >
  Content-creation skill ecosystem used in the SkillWeaver artifact. This
  scenario includes skills for source collection, content production, content
  optimization, and publication-oriented distribution workflows.
---

# Scene 2: Content Creation

This overview file summarizes the `datasets/s2-content-creation/` directory in
submission-friendly form. It is included to help reviewers understand the scope
of the bundled scenario; it is not required by the core discovery code.

## Directory Layout

```text
s2-content-creation/
|-- SKILL.md
|-- article-writer/
|-- audio-synthesizer/
|-- blog-writer/
|-- content-translator/
|-- content-writer/
|-- image-search/
|-- ppt-generator/
|-- seo-keyword-researcher/
|-- social-media-ops/
|-- social-poster/
|-- trend-analyzer/
|-- video-editor/
|-- video-editor-1/
|-- watermark-adder/
|-- web-scraper/
`-- wechat-publisher/
```

## Functional Grouping

### Source collection

| Folder | Exported skill | Primary role |
|------|------|------|
| `web-scraper` | Agent Browser | Web collection and browser automation |
| `image-search` | Image AI Kit | Image search and asset retrieval |
| `trend-analyzer` | Startup Idea Validator | Trend analysis and topic discovery |

### Content production

| Folder | Exported skill | Primary role |
|------|------|------|
| `article-writer` | Writing Plans | Article planning and drafting support |
| `audio-synthesizer` | Jarvis Vocal | Speech synthesis |
| `blog-writer` | Blog Writer | Blog drafting, rewriting, and review |
| `content-writer` | content-writer | Social-content generation |
| `ppt-generator` | AI PPT Generator | Slide generation |
| `video-editor` | Audio Video | Audio and video processing |
| `video-editor-1` | Video Editor | Video editing |

### Content optimization

| Folder | Exported skill | Primary role |
|------|------|------|
| `seo-keyword-researcher` | seo-keyword-researcher | SEO keyword research and article-brief preparation |
| `content-translator` | PDFMathTranslate | Translation |
| `watermark-adder` | Image Processor | Image post-processing and watermarking |

### Distribution and publication

| Folder | Exported skill | Primary role |
|------|------|------|
| `social-poster` | social-poster | Short social-copy distribution |
| `wechat-publisher` | wechat-content-creator | WeChat article preparation |
| `social-media-ops` | Social Media Ops | Social-media operations management |

## Case-Study Mapping

The included S2 case study uses the following three supporting skills:

- `seo-keyword-researcher/`
- `blog-writer/`
- `wechat-publisher/`

The `wechat-publisher/` folder exports the skill name `wechat-content-creator`,
which matches the dependency name used by the included case-study trigger skill.
