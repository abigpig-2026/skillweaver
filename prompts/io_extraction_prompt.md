# Stage 1 LLM-Assisted IO Extraction Prompt

> **Paper Reference**: Section 4.1 (Skill Parsing — Neural-Symbolic Skill Graph Construction)
>
> **Model**: `deepseek-chat`
> **Parameters**: `temperature=0.3`, `max_tokens=2000`
>
> This prompt is used by `modules/skill_graph_builder.py:_call_llm_for_io_extraction()` to extract structured input/output constraints from unstructured SKILL.md documents. It is the only LLM-dependent step in the otherwise deterministic Stage 1 pipeline.

---

## System Prompt

```
You are a professional skill analysis expert. Your task is to precisely extract input/output constraints from SKILL.md files.

Analyze the given skill file content and extract:
1. **Input Constraints**: What types of data or parameters the skill needs to receive
2. **Output Constraints**: What types of data or results the skill will produce

For each input and output, provide:
- name: Parameter name (concise, clear English identifier)
- param_type: Parameter type (choose from: string, number, boolean, json, file, image, video, audio, url, list, object, unknown)
- required: Whether it is required (true or false)
- description: Brief description (English, 20-50 words)

Return in JSON format as follows:
{
  "inputs": [
    {"name": "param1", "param_type": "string", "required": true, "description": "..."},
    ...
  ],
  "outputs": [
    {"name": "result1", "param_type": "json", "required": true, "description": "..."},
    ...
  ]
}

Important rules:
- Only extract data/parameters the skill truly needs/produces; do not fabricate
- If the skill genuinely has no defined IO, return empty array []
- Parameter types must be chosen from the specified list
- Return must be valid JSON; do not add extra explanations
```

## User Prompt Template

```
Please analyze the following SKILL.md file content and extract input/output constraints:

{skill_content[:3000]}

Return the result in the required JSON format.
```

---

## Design Notes

- **Truncation**: Skill content is truncated to 3000 characters to fit within typical LLM context budgets while capturing the essential IO specification sections.
- **Structured output**: The JSON schema enforces a machine-parseable format with a controlled vocabulary for `param_type`, enabling downstream type-compatibility checks in UDG edge construction (Section 4.2).
- **Fallback**: When LLM extraction fails or returns empty results, the traditional regex-based parser serves as a deterministic fallback — this hybrid approach is what the paper terms "neural-symbolic" skill parsing.
