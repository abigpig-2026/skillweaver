---
name: scene4-customer-service
description: >
  客户服务与运营场景（Customer Service & Operations）- 包含客户接触、信息处理、
  服务执行和跟进闭环等15个核心Skill。覆盖从邮件接收、聊天处理、客户画像到
  回复生成、合同审核、CRM更新的完整客户服务流程，新增客户支持、CRM管理、
  线索生成和客户反馈收集能力。适用于客户支持中心、销售运营、客户成功管理等场景。

  包含Skill：
  - 客户接触层：email-reader（邮件接收）、chatbot-handler（聊天处理）
  - 信息处理层：customer-profiler（客户画像）、faq-retriever（FAQ检索）、knowledge-searcher（知识搜索）
  - 服务执行层：response-generator（回复生成）、offer-drafter（报价起草）、contract-reviewer（合同审核）、solution-recommender（方案推荐）、customer-support（客户支持）
  - 跟进闭环层：followup-scheduler（跟进安排）、satisfaction-survey（满意度调查）、crm（CRM管理）、lead-generation（线索生成）、customer-feedback（客户反馈）

  使用场景：客户咨询自动回复、合同审核流程、报价方案生成、客户满意度跟踪、CRM线索管理等。
---

# 场景4：客户服务与运营（Customer Service & Operations）

## 概述

本场景包含15个精选Skill，覆盖客户服务与运营的完整工作流，从客户接触到跟进闭环形成完整服务链条。

## 目录结构

```
scene4-customer-service/
├── SKILL.md                          # 本文件
├── email-reader/                     # 邮件接收（Email Digest）
│   ├── SKILL.md
│   └── _meta.json
├── chatbot-handler/                  # 聊天处理（Alicloud AI Chatbot）
│   ├── SKILL.md
│   └── _meta.json
├── customer-profiler/                # 客户画像（Customer Segment）
│   ├── SKILL.md
│   └── _meta.json
├── faq-retriever/                    # FAQ检索（ima-skills）
│   └── SKILL.md
├── knowledge-searcher/               # 知识搜索（腾讯乐享知识库）
│   ├── SKILL.md
│   └── _meta.json
├── response-generator/               # 回复生成（Email Writer）
│   ├── SKILL.md
│   └── _meta.json
├── offer-drafter/                    # 报价起草（Contract Review）
│   ├── SKILL.md
│   └── _meta.json
├── contract-reviewer/                # 合同审核（Contract Review）
│   ├── SKILL.md
│   └── _meta.json
├── solution-recommender/             # 方案推荐（Contract Review Agent）
│   ├── SKILL.md
│   └── _meta.json
├── followup-scheduler/               # 跟进安排（Calendar Planner）
│   ├── SKILL.md
│   └── _meta.json
├── satisfaction-survey/              # 满意度调查（Employee Survey）
│   ├── SKILL.md
│   └── _meta.json
├── customer-support/                 # 客户支持（Customer Support）
│   ├── SKILL.md
│   └── _meta.json
├── crm/                              # CRM管理（CRM）
│   ├── SKILL.md
│   └── _meta.json
├── lead-generation/                  # 线索生成（Lead Generation）
│   ├── SKILL.md
│   └── _meta.json
└── customer-feedback/                # 客户反馈（Customer Feedback）
    ├── SKILL.md
    └── _meta.json
```

## Skill 详细说明

### 客户接触层（2个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| email-reader | Email Digest | 邮件接收与摘要生成 |
| chatbot-handler | Alicloud AI Chatbot | AI聊天机器人处理 |

### 信息处理层（3个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| customer-profiler | Customer Segment | 客户分群与画像 |
| faq-retriever | ima-skills | 知识库FAQ检索 |
| knowledge-searcher | 腾讯乐享知识库 Lexiang | 企业知识库搜索 |

### 服务执行层（5个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| response-generator | Email Writer | 客户回复邮件生成 |
| offer-drafter | Contract Review | 报价单与合同起草 |
| contract-reviewer | Contract Review | 合同审核与分析 |
| solution-recommender | Contract Review Agent | 解决方案推荐 |
| customer-support | Customer Support | 客户支持与工单处理 |

### 跟进闭环层（5个）

| 别名 | 来源Skill | 功能 |
|------|----------|------|
| followup-scheduler | Calendar Planner | 客户跟进日程安排 |
| satisfaction-survey | Employee Survey | 满意度调查 |
| crm | CRM | 客户关系管理与更新 |
| lead-generation | Lead Generation | 销售线索生成与跟踪 |
| customer-feedback | Customer Feedback | 客户反馈收集与分析 |

## 典型工作流

### 工作流1：客户咨询自动处理
```
email-reader → customer-profiler → faq-retriever → response-generator
```

### 工作流2：合同审核流程
```
contract-reviewer → offer-drafter → solution-recommender → followup-scheduler
```

### 工作流3：客户满意度管理
```
satisfaction-survey → customer-profiler → response-generator → followup-scheduler
```

### 工作流4：CRM线索管理
```
lead-generation → customer-profiler → crm → customer-feedback
```

## 安装与使用

每个子目录包含独立的Skill，可直接复制到Agent的skill目录下使用。
各Skill的具体使用方法请参阅各自的SKILL.md文件。
