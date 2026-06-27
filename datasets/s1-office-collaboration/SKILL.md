---
name: scene1-office-collaboration
description: >
  智能办公协作场景（Office Collaboration）- 包含邮件处理、日程管理、文档处理、
  内容生成、任务执行和办公辅助等17个核心Skill。覆盖从信息获取、文档处理、内容生成到执行操作的
  完整办公自动化流程，新增会议笔记、表格处理、文件整理和剪贴板等办公辅助能力。适用于每日报告循环、会议准备循环、邮件自动处理、日程管理等
  高频办公场景。

  包含Skill：
  - 信息获取层：email-reader（邮件读取）、calendar-query（日程查询）、rss-reader（RSS订阅）
  - 文档处理层：doc-reader（文档读取）、doc-translator（文档翻译）、ppt-generator（PPT生成）、excel-wps-table-diagnosis（表格诊断）
  - 内容生成层：email-writer（邮件写作）、report-writer（报告写作）、summarize（内容摘要）、data-analysis（数据分析）
  - 执行操作层：email-sender（邮件发送）、calendar-create（日程创建）、todo-tracker（任务跟踪）
  - 办公辅助层：meeting-notes-pro（会议笔记）、smart-file-organizer（文件整理）、clipboard-manager（剪贴板管理）

  使用场景：每日邮件摘要报告、会议材料准备、工作周报自动生成、任务跟踪管理、会议记录整理、文件智能分类等。
---

# 场景1：智能办公协作（Office Collaboration）

## 概述

本场景包含17个精选Skill，覆盖智能办公协作的完整工作流，从信息获取到执行操作形成闭环。

## 目录结构

```
scene1-office-collaboration/
├── SKILL.md                          # 本文件
├── email-reader/                     # 邮件读取（Email Digest）
│   ├── SKILL.md
│   └── _meta.json
├── calendar-query/                   # 日程查询（Caldav Calendar）
│   ├── SKILL.md
│   └── _meta.json
├── rss-reader/                       # RSS订阅（News）
│   ├── SKILL.md
│   └── _meta.json
├── doc-reader/                       # 文档读取（腾讯文档）
│   └── SKILL.md
├── doc-translator/                   # 文档翻译（PDFMathTranslate）
│   ├── SKILL.md
│   └── _meta.json
├── ppt-generator/                    # PPT生成（AI PPT Generator）
│   ├── SKILL.md
│   └── _meta.json
├── email-writer/                     # 邮件写作（Email Writer）
│   ├── SKILL.md
│   └── _meta.json
├── report-writer/                    # 报告写作（Work Report Writer）
│   ├── SKILL.md
│   └── _meta.json
├── summarize/                        # 内容摘要（Summarize）
│   ├── SKILL.md
│   └── _meta.json
├── data-analysis/                    # 数据分析（Data Analysis Reporting）
│   ├── SKILL.md
│   └── _meta.json
├── email-sender/                     # 邮件发送（Agentmail）
│   ├── SKILL.md
│   └── _meta.json
├── calendar-create/                  # 日程创建（Calendar Planner）
│   ├── SKILL.md
│   └── _meta.json
├── todo-tracker/                     # 任务跟踪（Todoist Manager）
│   ├── SKILL.md
│   └── _meta.json
├── meeting-notes-pro/                # 会议笔记（Meeting Notes Pro）
│   ├── SKILL.md
│   └── _meta.json
├── excel-wps-table-diagnosis/        # Excel/WPS表格诊断
│   ├── SKILL.md
│   └── _meta.json
├── smart-file-organizer/             # 智能文件整理（Smart File Organizer）
│   ├── SKILL.md
│   └── _meta.json
└── clipboard-manager/                # 剪贴板管理（Clipboard Manager）
    ├── SKILL.md
    └── _meta.json
```

## Skill 详细说明

### 信息获取层（3个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| email-reader | Email Digest | 检查邮件 inbox，生成邮件摘要 |
| calendar-query | Caldav Calendar | 查询日程安排，获取日历事件 |
| rss-reader | News | RSS订阅与热点追踪 |

### 文档处理层（4个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| doc-reader | 腾讯文档 | 腾讯文档读取与处理 |
| doc-translator | PDFMathTranslate | 文档翻译（支持PDF/Math） |
| ppt-generator | AI PPT Generator | AI生成PPT演示文稿 |
| excel-wps-table-diagnosis | Excel / WPS Table Diagnosis | Excel/WPS表格诊断与分析 |

### 内容生成层（4个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| email-writer | Email Writer | 邮件写作助手 |
| report-writer | Work Report Writer | 工作报告撰写 |
| summarize | Summarize | URL/文件/PDF/音频摘要 |
| data-analysis | Data Analysis Reporting | 数据分析与报告生成 |

### 执行操作层（3个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| email-sender | Agentmail | 邮件发送（Python脚本） |
| calendar-create | Calendar Planner | 日程创建与管理 |
| todo-tracker | Todoist Manager | 任务跟踪与管理 |

### 办公辅助层（3个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| meeting-notes-pro | Meeting Notes Pro | 会议笔记记录与整理 |
| smart-file-organizer | Smart File Organizer | 智能文件分类与整理 |
| clipboard-manager | Clipboard Manager | 剪贴板历史管理与同步 |

## 典型工作流

### 工作流1：每日邮件报告循环
```
email-reader → summarize → report-writer → email-sender
```

### 工作流2：会议准备循环
```
calendar-query → doc-reader → ppt-generator → calendar-create
```

### 工作流3：任务跟踪管理
```
todo-tracker → email-writer → email-sender → calendar-create
```

## 安装与使用

每个子目录包含独立的Skill，可直接复制到Agent的skill目录下使用。
各Skill的具体使用方法请参阅各自的SKILL.md文件。
