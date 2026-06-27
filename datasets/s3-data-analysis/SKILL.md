---
name: scene3-data-analysis
description: >
  数据分析与决策场景（Data Analysis & Decision）- 包含数据采集、数据处理、分析洞察和
  决策执行等19个核心Skill。覆盖从API数据获取、数据清洗、异常检测到可视化报告和
  流程触发的完整数据分析 pipeline，新增数据分析师、图表生成、商业智能和SQL查询审查能力。
  适用于企业数据监控、业务报表生成、决策支持等场景。

  包含Skill：
  - 数据采集层：api-fetcher（API数据获取）、db-connector（数据库连接）、log-collector（日志收集）、file-importer（文件导入）
  - 数据处理层：data-cleaner（数据清洗）、transform-engine（数据转换）、feature-extractor（特征提取）、anomaly-detector（异常检测）、sql-query-reviewer（SQL查询审查）
  - 分析洞察层：visualizer（可视化）、report-generator（报告生成）、competitor-analyzer（竞争分析）、forecast-engine（预测引擎）、data-analyst（数据分析师）、chart-gen（图表生成）、business-intelligence（商业智能）
  - 决策执行层：alert-sender（告警发送）、dashboard-updater（看板更新）、workflow-trigger（流程触发）

  使用场景：业务数据监控循环、自动化报表生成、异常告警与处理、竞争情报分析、商业智能分析等。
---

# 场景3：数据分析与决策（Data Analysis & Decision）

## 概述

本场景包含19个精选Skill，覆盖数据分析与决策的完整pipeline，从数据采集到决策执行形成闭环。

## 目录结构

```
scene3-data-analysis/
├── SKILL.md                          # 本文件
├── api-fetcher/                      # API数据获取（Data Quality Check）
│   ├── SKILL.md
│   └── _meta.json
├── db-connector/                     # 数据库连接（Data Analysis Reporting）
│   ├── SKILL.md
│   └── _meta.json
├── log-collector/                    # 日志收集（Data Quality Check）
│   ├── SKILL.md
│   └── _meta.json
├── file-importer/                    # 文件导入（PDF Markdown Converter）
│   ├── SKILL.md
│   └── _meta.json
├── data-cleaner/                     # 数据清洗（Data Quality Check）
│   ├── SKILL.md
│   └── _meta.json
├── transform-engine/                 # 数据转换（PDF Markdown Converter）
│   ├── SKILL.md
│   └── _meta.json
├── feature-extractor/                # 特征提取（Vision Helper - AI Image Analysis）
│   ├── SKILL.md
│   └── _meta.json
├── anomaly-detector/                 # 异常检测（Inventory Anomaly）
│   ├── SKILL.md
│   └── _meta.json
├── visualizer/                       # 可视化（Mindmap）
│   ├── SKILL.md
│   └── _meta.json
├── report-generator/                 # 报告生成（Daily Business Report）
│   ├── SKILL.md
│   └── _meta.json
├── competitor-analyzer/              # 竞争分析（Startup Idea Validator）
│   ├── SKILL.md
│   └── _meta.json
├── forecast-engine/                  # 预测引擎（AI Data Analyst CN）
│   ├── SKILL.md
│   └── _meta.json
├── alert-sender/                     # 告警发送（Email Writer）
│   ├── SKILL.md
│   └── _meta.json
├── dashboard-updater/                # 看板更新（Project Planning）
│   ├── SKILL.md
│   └── _meta.json
├── workflow-trigger/                 # 流程触发（Workflow Diagram）
│   ├── SKILL.md
│   └── _meta.json
├── data-analyst/                     # 数据分析师（Data Analyst）
│   ├── SKILL.md
│   └── _meta.json
├── chart-gen/                        # 图表生成器（Chart Generator）
│   ├── SKILL.md
│   └── _meta.json
├── business-intelligence/            # 商业智能（Business Intelligence）
│   ├── SKILL.md
│   └── _meta.json
└── sql-query-reviewer/               # SQL查询审查（SQL Query Reviewer）
    ├── SKILL.md
    └── _meta.json
```

## Skill 详细说明

### 数据采集层（4个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| api-fetcher | Data Quality Check | API数据获取与质量检查 |
| db-connector | Data Analysis Reporting | 数据库连接与查询分析 |
| log-collector | Data Quality Check | 日志收集与数据质量检查 |
| file-importer | PDF Markdown Converter | 文件导入与格式转换 |

### 数据处理层（5个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| data-cleaner | Data Quality Check | 数据清洗与质量验证 |
| transform-engine | PDF Markdown Converter | 数据格式转换 |
| feature-extractor | Vision Helper | AI图像分析与特征提取 |
| anomaly-detector | Inventory Anomaly | 异常检测与告警 |
| sql-query-reviewer | SQL Query Reviewer | SQL查询审查与优化 |

### 分析洞察层（7个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| visualizer | Mindmap | 数据可视化与思维导图 |
| report-generator | Daily Business Report | 业务报告自动生成 |
| competitor-analyzer | Startup Idea Validator | 竞争分析与市场调研 |
| forecast-engine | AI Data Analyst CN | AI数据分析与预测 |
| data-analyst | Data Analyst | 专业数据分析与洞察 |
| chart-gen | Chart Generator | 图表生成与数据可视化 |
| business-intelligence | Business Intelligence | 商业智能与决策支持 |

### 决策执行层（3个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| alert-sender | Email Writer | 告警邮件发送 |
| dashboard-updater | Project Planning | 项目计划与看板更新 |
| workflow-trigger | Workflow Diagram | 工作流程触发与管理 |

## 典型工作流

### 工作流1：数据监控循环
```
api-fetcher → data-cleaner → anomaly-detector → alert-sender → dashboard-updater
```

### 工作流2：自动化报表循环
```
db-connector → visualizer → report-generator → workflow-trigger
```

### 工作流3：竞争情报分析
```
competitor-analyzer → forecast-engine → report-generator → alert-sender
```

### 工作流4：商业智能分析
```
data-analyst → chart-gen → business-intelligence → dashboard-updater
```

## 安装与使用

每个子目录包含独立的Skill，可直接复制到Agent的skill目录下使用。
各Skill的具体使用方法请参阅各自的SKILL.md文件。
