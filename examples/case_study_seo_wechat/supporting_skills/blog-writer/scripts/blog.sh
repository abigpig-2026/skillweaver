#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-help}"
shift || true
INPUT="$*"

print_block() {
  cat
  if [ -n "$INPUT" ]; then
    printf "\nInput:\n%s\n" "$INPUT"
  fi
}

show_help() {
  cat <<'EOF'
Blog Writer

Usage:
  bash scripts/blog.sh <command> "<content>"

Commands:
  write      Generate a complete blog post draft in Markdown
  outline    Generate three alternative article outlines
  seo        Review draft content and suggest SEO improvements
  hook       Generate five opening-hook variants
  series     Plan a 10-post content series
  rewrite    Rewrite supplied content in a specified style
  cta        Generate multiple CTA variants
  help       Show this help message
EOF
}

case "$CMD" in
  write)
    print_block <<'PROMPT'
You are a senior content writer and SEO editor.
Write a complete blog post in Markdown for the provided topic.

Requirements:
1. Create an SEO-friendly title.
2. Write an introduction that establishes the problem and value.
3. Organize the main body into 3-5 sections with clear subheadings.
4. Include practical examples, evidence, or concrete guidance where helpful.
5. End with a concise conclusion and a clear call to action.
6. Keep the writing informative rather than verbose.
PROMPT
    ;;
  outline)
    print_block <<'PROMPT'
You are a content strategist.
Produce three alternative article outlines for the provided topic.

For each outline, include:
1. A working title.
2. The target audience.
3. The main angle.
4. A section-by-section structure.
5. A short keyword list.
PROMPT
    ;;
  seo)
    print_block <<'PROMPT'
You are an SEO reviewer.
Analyze the provided draft and return actionable SEO suggestions.

Check:
1. Title quality and keyword placement.
2. Opening paragraph clarity.
3. Section structure and heading quality.
4. Keyword coverage and repetition risk.
5. Internal-link or CTA opportunities.
6. A short prioritized improvement list.
PROMPT
    ;;
  hook)
    print_block <<'PROMPT'
You are an editorial copywriter.
Generate five different opening hooks for the provided topic.

Vary the styles across:
1. Data-driven opening.
2. Story-driven opening.
3. Question-driven opening.
4. Contrarian opening.
5. Benefit-led opening.
PROMPT
    ;;
  series)
    print_block <<'PROMPT'
You are a content program manager.
Plan a 10-post blog series for the provided topic.

Return:
1. Series title.
2. Target audience.
3. Ten post titles with brief angles.
4. Suggested publication order.
5. Internal-linking suggestions across the series.
PROMPT
    ;;
  rewrite)
    print_block <<'PROMPT'
You are an editorial rewriter.
Rewrite the provided draft in the requested style while preserving its core meaning.

Return:
1. The rewritten article.
2. A short note on the main style changes.
3. Any content areas that still need factual review.
PROMPT
    ;;
  cta)
    print_block <<'PROMPT'
You are a conversion copywriter.
Generate five CTA variants for the provided product, service, or article.

Vary the styles across urgency, value, credibility, curiosity, and low-friction action.
PROMPT
    ;;
  help|-h|--help)
    show_help
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    show_help >&2
    exit 1
    ;;
esac
