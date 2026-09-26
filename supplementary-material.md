# Supplementary Material — Paper #1840

We thank the reviewers for their constructive questions and comments. This supplement
is organized into five sections (DATA-1 … DATA-5), each addressing one or more
reviewer questions. The full source code is available in our repository:
https://anonymous.4open.science/r/skillweaver-B9F9/

| Section | Answers          | Content                                                      |
| ------- | ---------------- | ------------------------------------------------------------ |
| DATA-1  | A-Q1, B-Q5, C-Q4 | UDG construction, cycle-filtering parameters, cycle enumeration & deduplication, scalability |
| DATA-2  | A-W2, C-W3       | UDG construction derivation (dependency components)          |
| DATA-3  | A-Q2, A-W3, C-W2 | Live-execution stability (repeated runs)                     |
| DATA-4  | A-W1, B-Q3       | Parsing accuracy and cycle-discovery validation              |
| DATA-5  | B-Q4             | Type label & name identifier for type compatibility          |

---

## DATA-1 — UDG Construction and Cycle-Filtering Parameters

### 1.1 Edge-retention thresholds

SkillWeaver builds a *Unified Dependency Graph (UDG)* in three stages: (1) an
independent sub-graph per skill, (2) pairwise sub-graph matching to derive
cross-skill edges, and (3) assembly of the global weighted directed graph. A
directed edge a_i → a_j between two action nodes is retained **iff** all
three thresholds are satisfied:

$$
t_{ij} \ge \tau_t \;\wedge\; c_{ij} \ge \rho \;\wedge\; \Phi(a_i,a_j) \ge \eta,
$$

where t_ij is the type-compatibility (parameter affinity), c_ij the input
completeness, and Φ the combined dependency score (see DATA-2). The default
configuration and the role of each parameter:

| Parameter                    | Symbol | Default | Meaning                                                      |
| ---------------------------- | -----: | ------: | ------------------------------------------------------------ |
| type-compat threshold        |    τ_t |     0.3 | minimum type-affinity for an edge                            |
| input-completeness threshold |      ρ |     0.3 | minimum fraction of a_j's required inputs that a_i can satisfy |
| dependency-score threshold   |      η |    0.44 | minimum combined score Φ for an edge                         |
| input-match threshold        |    τ_m |     0.3 | minimum `compat` for counting one input as matched in c_ij   |

These thresholds jointly determine which candidate edges survive and therefore
which cycles are discoverable. In the paper's main experiments we use the default
configuration above.

### 1.2 Cycle enumeration and deduplication

Cycles are enumerated on the action-node-level UDG (Algorithm 1 in the paper):

1. **Graph construction** — build a `networkx.DiGraph` over all action nodes, with
   edge weight set to the affinity score Φ.
2. **Strongly connected components** — compute all SCCs via Tarjan's algorithm and
   retain those with size ≥ 2 (a simple cycle cannot span a trivial SCC).
3. **Johnson's simple-cycle enumeration** — on each retained SCC, enumerate simple
   cycles with hop count k ∈ [min_hop=3, length_bound=6].
4. **Deduplication by rotation** — the same cycle is enumerated from multiple
   starting nodes; we normalize each cycle by rotating it so its lexicographically
   smallest node id is first, and drop duplicates.
5. **Resolution** — each deduplicated cycle is resolved into a `CyclicPath` carrying
   its skill sequence, per-edge affinity, and average semantic similarity.

A per-SCC batch mode (processing one SCC at a time and releasing memory) is
provided for large graphs.

### 1.3 Parameter sensitivity across configurations

We analyze four design dimensions that most affect graph density — the
dependency-score threshold η, the weights α:β:γ, the hop bounds
`(min_hop, length_bound)`, and the `max_unique_skills` cap — over all four
scenarios. We empirically perturb η and the weighting scheme (treated as a
**joint configuration**: each setting fixes both, table below), while separately
examining the fixed hop and skill-count constraints (not swept because their
physical meaning is fixed). To isolate the effect of η and the weights from stage-1 randomness, we fix the
paper's stage-1 parsing output — the same 67-skill / 243-action inventory used to
produce Table I — and, for each perturbation, re-run only the UDG construction and
cycle enumeration while holding the parsed skills and actions fixed. The cycle
counts below are therefore directly observed, not rescaled.

**Theoretical analysis: why balanced signals avoid single-signal collapse.** The three
signals provide complementary evidence for dependency inference: type compatibility t_ij
captures data-form compatibility, input completeness c_ij measures required-input coverage,
and semantic relatedness s_ij helps suppress task-irrelevant matches. Because Φ combines
these signals, no single component alone guarantees a valid dependency:

- **type (α)**: type compatibility alone cannot establish that the semantics should flow.
  The `type_score` matrix assigns the top score 1.0 to same-type pairs (e.g. `string→string`,
  `file→file`), and `string` is the most frequent type in the parameter pool — type reflects
  only that the data *forms* match, not whether this string is the semantic content a_j
  actually wants. It is a **wide gate**: it filters only blatantly clashing types while
  admitting a mass of "type-compatible but semantically unrelated" noise edges.
- **semantic (γ)**: semantic relatedness alone cannot establish a connected data flow. Two
  skills may both mention "email" — one sends, one archives — with no real dependency
  between them.
- **completeness (β)**: c_ij is a **gate** — once satisfied (c_ij→1) it stops contributing
  discrimination, and all passing edges converge on this signal.

The balanced weights (0.35:0.35:0.30) force every edge to draw on all three signals rather
than letting any single one dominate; the sensitivity results below further show that
heavily biasing one signal reduces retained-cycle coverage and/or live activation
effectiveness. η is the density knob: η↓ admits more weakly supported edges, whereas η↑
retains only higher-scoring edges at the cost of coverage.

**Joint configuration and sensitivity results.** η and the weights are one joint
configuration — every runnable setting fixes both. We perturb around the default point
(η=0.44, 0.35:0.35:0.30) by lowering/raising η alone (weights fixed) or biasing one weight
alone (η fixed). For each configuration we report, side by side, three quantities: **retained-cycle
coverage** (Retained cycles, obtained by re-running UDG construction and cycle enumeration on
the fixed stage-1 parsing output) and **sampled activation effectiveness** (AR and successful-run CAF from
sampling 20 cycles for live execution on S1 + OpenClaw + Qwen3.5-Plus). Because AR and CAF are
measured on S1 only (n=20) while Retained cycles spans all four scenarios, we report the three
in parallel rather than folding them into a single combined product:

| Configuration           |    η | Weights α:β:γ  | Retained cycles | AR (S1, n=20) | Success CAF |
| :---------------------- | ---: | :------------- | --------------: | ------------: | ----------: |
| default (balanced)      | 0.44 | 0.35:0.35:0.30 |       **1,053** |           60% |       21.3x |
| η lowered               | 0.40 | 0.35:0.35:0.30 |           1,137 |           55% |       19.1x |
| η raised                | 0.48 | 0.35:0.35:0.30 |             287 |           65% |       22.0x |
| α biased (type)         | 0.44 | 0.45:0.30:0.25 |             214 |           20% |        7.8x |
| β biased (completeness) | 0.44 | 0.25:0.40:0.35 |           1,053 |           50% |       18.5x |
| γ biased (semantic)     | 0.44 | 0.30:0.35:0.35 |             269 |           25% |        9.8x |

**Joint judgment.** Reading coverage, AR, and CAF side by side, the default configuration keeps
the full 1,053-cycle coverage while sustaining high activation effectiveness (AR 60%, CAF 21.3x),
whereas every perturbed configuration sacrifices at least one of the three:

- **α biased (type)** reduces retained cycles to 214 and AR to 20%, with success CAF of
  7.8x, indicating that overweighting type compatibility degrades both cycle coverage and
  live activation effectiveness.
- **γ biased (semantic)** similarly reduces retained cycles to 269 and AR to 25%, with
  success CAF of 9.8x.
- **η raised (0.48)** raises AR to 65% and CAF to 22.0x by survivor bias, but coverage collapses
  from 1,053 to 287 (missing 73%) — it discards too many mid-score edges.
- **η lowered (0.40)** admits 8% more weak edges (1,137), but those weak cycles activate poorly:
  AR drops to 55%, CAF to 19.1x — the lowering is mild, but gainless.
- **β biased (completeness)** weakens the discriminating type signal with no compensation from
  a saturated c_ij: AR 50%, CAF 18.5x.
- The response is **asymmetric** (mild +8% when lowered, cliff-like −73%~−80% when raised or
  α/γ biased): lowering η gently admits a few weak edges, while raising it (or biasing a single
  weight) collapses the dense scenarios' edges and their cycles together.

Taken together, among the tested configurations, the default parameters (η=0.44,
α:β:γ=0.35:0.35:0.30) provide a balanced trade-off between retained-cycle coverage and
live activation effectiveness. The complementary roles of the three signals offer a
qualitative account of this behavior. This is an empirical observation over the
tested configurations rather than a claim of global optimality.

**Hop bounds.** We treat the hop bounds primarily as scope constraints rather than
tunable parameters, and examine their boundary choices separately:

- **Lower bound `min_hop=3` (excludes hop=2).** A 2-hop cycle contains only two action
  transitions and represents direct pairwise alternation (A↔B). Our evaluation focuses on
  multi-stage loops with at least three action nodes/hops; this does not exclude cycles
  involving two distinct skills when they contain three or more action stages. Under this
  scope, hop=2 neither fits the multi-stage loop we target nor belongs to our attack
  surface; `min_hop=3` is a requirement of the definition, not a tunable knob.

- **Upper bound `length_bound=6` (excludes hop=7).** Longer-hop cycles accumulate
  more layers of cross-skill input/output mismatch and semantic drift per hop. Note
  that 3–6 hops is the evaluation scope of this paper: RQ2 samples candidates from
  within this range, so the live-execution results do not by themselves rule out the
  activation of 7-hop cycles. Within this scope enumeration completes and the
  semantics stay interpretable, making 6 the natural upper bound.

- **3–6 hop already carries the conclusion.** All 1,053 retained candidate cycles reported
  in the paper fall within hop∈[3,6], with a long-tailed depth distribution (k=4 at
  57.5%, k=6 at 24.2%, k=3 at 10.4%, the rest k=5) — retained candidate cycles concentrate
  in the mid-depth range. The reported cycle-discovery results are therefore fully
  characterized within the 3–6 hop evaluation scope, and the hop=2 boundary exclusion
  (out-of-scope pairwise alternation) does not affect it.

**`max_unique_skills`.** The upper bound is a substantive constraint, not a vacuous
cap. Raising it from 4 to 5 leaves the count unchanged at **1,053** (no retained cycle
contains 5+ distinct skills), but lowering it to 3 removes the 486 four-skill cycles
(S1 247, S2 169, S4 70) and cuts the count to 567 (−46%). The cap therefore selects
the four-skill cycles that define the compositional attack surface.

### 1.4 Scalability discussion

At the paper's scale (67 skills, 243 action nodes, 1,865 retained edges; Table I),
the full pipeline — Tarjan SCC decomposition plus per-SCC, per-hop Johnson
simple-cycle enumeration — completes in seconds (measured 0.4–18 s across the four
scenarios, including the per-SCC batch mode that releases memory between
components). The complexity is Tarjan O(V+E) plus Johnson
O((V_s+E_s)(C_s+1)) per SCC, where C_s is that SCC's simple-cycle count;
with `length_bound=6` the per-layer enumeration is O(V^6), a constant-degree bound
that keeps each layer tractable.

The real bottleneck is **graph density**, not node count: when η is too low, a
dense scenario (order-10³ edges) makes the cycle count explode past the enumeration
limit. η directly controls graph density and therefore also affects enumeration
cost. Guardrails are (i) `length_bound=6`, (ii) the global η threshold,
and (iii) a cycle-count overflow cap. For ecosystems scaling to 10³+ skills, edge
pruning (affinity top-k) or community detection reduces pairwise matching from
O(N^2) to O(N k); the layered `SkillSubGraph` / `global_action_nodes` structure
already reserves this extension point.

---

## DATA-2 — UDG Construction Derivation

### 2.1 Dependency components

For a source action a_i (outputs O(a_i)) and a target action a_j (inputs
I(a_j)), three components are derived:

**Type affinity t_ij** — the maximum parameter-level compatibility over all
output/input pairs:

$$
t_{ij} = \max_{p \in O(a_i),\, q \in I(a_j)} \mathrm{compat}(p, q),
$$

$$
\mathrm{compat}(p,q) = 0.6 \cdot \mathrm{type\_score}(p,q) + 0.4 \cdot \mathrm{name\_score}(p,q).
$$

**Input completeness c_ij** — the fraction of a_j's *required* inputs that at
least one output of a_i can satisfy (with compat ≥ τ_m):

$$
c_{ij} = \frac{\left|\{ q \in I_{\mathrm{req}}(a_j) : \exists p \in O(a_i),\; \mathrm{compat}(p,q) \ge \tau_m \}\right|}{|I_{\mathrm{req}}(a_j)|},
$$

with c_ij=1 when a_j has no required inputs.

**Semantic similarity s_ij** — computed from the textual representations of the
action description, parameter descriptions, and surrounding workflow context.
TF-IDF cosine similarity is used to measure the similarity between these
representations, encoded by a `TfidfVectorizer` with word n-gram range (1,2),
sub-linear TF scaling, and 10,000 features.

### 2.2 Combination

The three components are combined into the dependency score:

$$
\Phi(a_i, a_j) = 0.35 \cdot t_{ij} + 0.35 \cdot c_{ij} + 0.30 \cdot s_{ij}.
$$

The weights (0.35 / 0.35 / 0.30) reflect that parameter-level type compatibility
and input completeness carry the primary signal, with a slightly lower weight on
semantic similarity.

### 2.3 Type-compatibility matrix and name rule

`type_score` is a hand-crafted soft matrix over the type labels (extracted by the
stage-1 parser). Unknown types are handled by a downgrade strategy rather than a
hard zero, to avoid falsely eliminating legitimate edges:

| output → input          | score |      | output → input                      | score |
| ----------------------- | ----- | ---- | ----------------------------------- | ----- |
| string → string         | 1.0   |      | url → url                           | 1.0   |
| json → json             | 1.0   |      | file → file                         | 1.0   |
| number → number         | 1.0   |      | boolean → boolean                   | 1.0   |
| string → json           | 0.8   |      | json → string                       | 0.9   |
| string → url            | 0.7   |      | url → string                        | 0.9   |
| string → file           | 0.6   |      | file → string                       | 0.8   |
| number → string         | 0.8   |      | boolean → string                    | 0.7   |
| unknown → unknown       | 0.5   |      | unknown → {string,json}             | 0.4   |
| {string,json} → unknown | 0.4   |      | unknown → number / number → unknown | 0.3   |
| (any other pair)        | 0.3   |      |                                     |       |

`name_score` follows a three-valued rule on the (lower-cased) parameter names:
0.8 if one name is a substring of the other, 0.5 if a word of the input name occurs
in the output name, and 0 otherwise.

---

## DATA-3 — Live-Execution Stability (Repeated Runs)

### 3.1 Full re-execution and reproducibility

The paper's RQ2 evaluates each attack once across the reported platform–model
configurations. For the repeated-run analysis, we focus on the
OpenClaw + Qwen3.5-Plus configuration and re-execute all 110 paths (S1:35, S2:20,
S3:40, S4:15) under identical settings (same platform, model, fresh session each),
so every path has a pair of runs. The table below reports, per scenario, the paper's
CAF and AR alongside the re-run CAF (mean ± std) over successfully activated paths,
together with the re-run 95% confidence interval:

**Per scenario (each path executed twice; CAF computed over successfully activated paths):**

| Scenario                | Paths | n_success | Paper CAF | Re-run CAF (mean±std) |  Re-run 95% CI | Paper AR | Re-run AR |
| ----------------------- | ----: | --------: | --------: | --------------------: | -------------: | -------: | --------: |
| S1 Office Collaboration |    35 |        18 |     21.1x |          17.23 ± 4.68 | [15.07, 19.39] |    51.4% |     51.4% |
| S2 Content Creation     |    20 |        12 |     18.9x |          17.87 ± 3.05 | [16.14, 19.60] |    60.0% |     60.0% |
| S3 Data Analysis        |    40 |        14 |     22.4x |          19.37 ± 4.51 | [17.01, 21.73] |    35.0% |     35.0% |
| S4 Customer Service     |    15 |        10 |     17.3x |          19.50 ± 6.56 | [15.43, 23.57] |    66.7% |     66.7% |

Here n_success is the number of paths successfully activated in the re-run (completing
at least one full closed-loop traversal), so Re-run AR = n_success / Paths; Paper AR is
the activation rate reported in the paper's Table II. The 95% CI is computed as mean ±
1.96·s/√n over the n_success successful paths in the re-run; it characterizes the spread
of CAF across the successfully activated attacks, **not** the run-to-run variability of
any single path. The scenario-level change in mean CAF is reflected by the Paper CAF and
Re-run CAF columns (S1–S3 lower by 1.0–3.9x, S4 higher by 2.2x). All reported intervals
remain well above CAF=1, and the re-run mean (17.23x–19.50x) sits in the same amplification
regime as the paper's reported results (17.3x–22.4x): S1–S3 are slightly lower in the re-run
and S4 slightly higher — variation observed across the two executions that does not change
the core finding of 17–22× token amplification.

### 3.2 CAF definition and handling of failed runs

We report CAF over *successfully activated* paths (i.e., paths completing at least one full closed-loop traversal), because CAF measures
the resource amplification produced by a complete attack cycle; a failed path may abort
at different stages *before* the cycle closes, so its token consumption is not directly
comparable as cycle-level amplification. This matches the paper, which reports the mean
CAF over triggered (activated) closed-loop attacks (Table II), rather than an average
over all attempts.

---

## DATA-4 — Parsing Accuracy and Cycle-Discovery Validation

### 4.1 Stage-1 skill parsing accuracy (I/O extraction)

The first stage of cycle discovery is the LLM-based I/O extraction over each skill's
`SKILL.md`. We measure its precision / recall / F1 / type-accuracy against a
human-reviewed ground truth over all **67 skills** (4 scenarios), produced by three
annotators who independently review each skill and resolve disagreements by majority
vote. An entry counts as
I/O if the skill actually receives or produces it, including business parameters,
credentials, environment variables, file paths, and URLs.

**Overall**

| Metric        | Micro |
| ------------- | ----: |
| Precision     | 0.992 |
| Recall        | 0.808 |
| F1            | 0.891 |
| Type accuracy | 0.975 |

Micro statistics aggregate over all 67 skills. We report micro (and per-scenario
micro) only: per-skill (macro) averaging would mix skills with different denominators
— empty-extraction skills have undefined precision — and micro already fully answers
the extraction precision/recall question.

The refinement extracts **398 entries**, of which **395** are correct and **3**
incorrect; annotators added **94** missing entries. Type labels agree on **385/395**
of the correct entries.

**Per-scenario (micro)**

| Scenario                | Skills | Precision | Recall |
| ----------------------- | -----: | --------: | -----: |
| S1 Office Collaboration |     17 |     0.984 |  0.803 |
| S2 Content Creation     |     16 |       1.0 |  0.780 |
| S3 Data Analysis        |     19 |       1.0 |  0.842 |
| S4 Customer Service     |     15 |     0.984 |  0.805 |

**Empty-extraction breakdown**

- **True-empty** (2): no data I/O exists, the parser correctly extracted nothing —
  `customer-feedback`, `customer-support`.
- **Missed** (10): the parser returned an empty schema although I/O exists (54 entries
  added by humans): `calendar-create`, `doc-translator`, `content-translator`,
  `social-media-ops`, `business-intelligence`, `dashboard-updater`, `faq-retriever`,
  `followup-scheduler`, `knowledge-searcher`, `satisfaction-survey`.

**Per-skill detail**

| Scenario | Folder                      | Skill name                                 | #Ext | #Corr | #Wrong | #Add |     P |     R | Type acc |
| -------- | --------------------------- | ------------------------------------------ | ---: | ----: | -----: | ---: | ----: | ----: | -------: |
| s1       | `calendar-create`           | Calendar Planner                           |    0 |     0 |      0 |    4 |     — | 0.000 |        — |
| s1       | `calendar-query`            | caldav-calendar                            |   12 |    12 |      0 |    3 | 1.000 | 0.800 |    1.000 |
| s1       | `clipboard-manager`         | clipboard-manager                          |    7 |     7 |      0 |    1 | 1.000 | 0.875 |    1.000 |
| s1       | `data-analysis`             | data-analysis-reporting                    |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `doc-reader`                | tencent-docs                               |    6 |     6 |      0 |    5 | 1.000 | 0.545 |    1.000 |
| s1       | `doc-translator`            | PDFMathTranslate                           |    0 |     0 |      0 |    3 |     — | 0.000 |        — |
| s1       | `email-reader`              | EmailDigest Daily Email Summary for Agents |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `email-sender`              | python-agentmail-send-receive              |    4 |     2 |      2 |    6 | 0.500 | 0.250 |    1.000 |
| s1       | `email-writer`              | email-writer                               |   11 |    11 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `excel-wps-table-diagnosis` | excel-wps-table-diagnosis                  |    9 |     9 |      0 |    0 | 1.000 | 1.000 |    0.444 |
| s1       | `meeting-notes-pro`         | meeting-notes-pro                          |    9 |     9 |      0 |    2 | 1.000 | 0.818 |    1.000 |
| s1       | `ppt-generator`             | ppt-maker                                  |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    0.800 |
| s1       | `report-writer`             | work-report-writer                         |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `rss-reader`                | News                                       |    6 |     6 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `smart-file-organizer`      | file-organizer                             |    4 |     4 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s1       | `summarize`                 | summarize                                  |   10 |    10 |      0 |    6 | 1.000 | 0.625 |    1.000 |
| s1       | `todo-tracker`              | todoist                                    |   26 |    26 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `article-writer`            | writing-plans                              |    1 |     1 |      0 |    1 | 1.000 | 0.500 |    1.000 |
| s2       | `audio-synthesizer`         | jarvis-vocal                               |    7 |     7 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `blog-writer`               | Blog Writer                                |   12 |    12 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `content-translator`        | PDFMathTranslate                           |    0 |     0 |      0 |    4 |     — | 0.000 |        — |
| s2       | `content-writer`            | content-writer                             |    7 |     7 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `image-search`              | image-ai-kit                               |    4 |     4 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `ppt-generator`             | ppt-maker                                  |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `seo-keyword-researcher`    | seo-keyword-researcher                     |    8 |     8 |      0 |    0 | 1.000 | 1.000 |    0.625 |
| s2       | `social-media-ops`          | social-media-ops                           |    0 |     0 |      0 |   17 |     — | 0.000 |        — |
| s2       | `social-poster`             | social-poster                              |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `trend-analyzer`            | startup-idea-validator                     |    8 |     8 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `video-editor`              | audio-video                                |    7 |     7 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `video-editor-1`            | video-editor                               |   15 |    15 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s2       | `watermark-adder`           | image-processor                            |    1 |     1 |      0 |    1 | 1.000 | 0.500 |    1.000 |
| s2       | `web-scraper`               | Agent Browser                              |   11 |    11 |      0 |    5 | 1.000 | 0.688 |    1.000 |
| s2       | `wechat-publisher`          | wechat-content-creator                     |    8 |     8 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `alert-sender`              | email-writer                               |   12 |    12 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `anomaly-detector`          | inventory-anomaly-prediction               |   11 |    11 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `api-fetcher`               | data-quality-check                         |    5 |     5 |      0 |    1 | 1.000 | 0.833 |    1.000 |
| s3       | `business-intelligence`     | Business Intelligence                      |    0 |     0 |      0 |    6 |     — | 0.000 |        — |
| s3       | `chart-gen`                 | chartgen                                   |   10 |    10 |      0 |    1 | 1.000 | 0.909 |    1.000 |
| s3       | `competitor-analyzer`       | startup-idea-validator                     |    3 |     3 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `dashboard-updater`         | project-planning                           |    0 |     0 |      0 |    7 |     — | 0.000 |        — |
| s3       | `data-analyst`              | data-analyst                               |    8 |     8 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `data-cleaner`              | data-quality-check                         |    5 |     5 |      0 |    1 | 1.000 | 0.833 |    1.000 |
| s3       | `db-connector`              | data-analysis-reporting                    |    6 |     6 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `feature-extractor`         | vision-helper                              |    4 |     4 |      0 |    2 | 1.000 | 0.667 |    1.000 |
| s3       | `file-importer`             | pdf-markdown-converter                     |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `forecast-engine`           | ai-data-analyst-cn                         |    6 |     6 |      0 |    1 | 1.000 | 0.857 |    1.000 |
| s3       | `log-collector`             | data-quality-check                         |    5 |     5 |      0 |    1 | 1.000 | 0.833 |    1.000 |
| s3       | `report-generator`          | daily-business-report                      |   10 |    10 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `sql-query-reviewer`        | sql-query-reviewer                         |    6 |     6 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `transform-engine`          | pdf-markdown-converter                     |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s3       | `visualizer`                | MindMap                                    |    6 |     6 |      0 |    1 | 1.000 | 0.857 |    1.000 |
| s3       | `workflow-trigger`          | workflow-diagram                           |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s4       | `chatbot-handler`           | alicloud-ai-chatbot                        |    7 |     7 |      0 |    1 | 1.000 | 0.875 |    1.000 |
| s4       | `contract-reviewer`         | contract-review                            |    7 |     7 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s4       | `crm`                       | CRM                                        |    8 |     8 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s4       | `customer-feedback`         | customer-feedback                          |    0 |     0 |      0 |    0 |     — |     — |        — |
| s4       | `customer-profiler`         | customer-segmentation                      |    6 |     6 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s4       | `customer-support`          | Customer Support                           |    0 |     0 |      0 |    0 |     — |     — |        — |
| s4       | `email-reader`              | EmailDigest Daily Email Summary for Agents |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    0.800 |
| s4       | `faq-retriever`             | ima-skill                                  |    0 |     0 |      0 |    4 |     — | 0.000 |        — |
| s4       | `followup-scheduler`        | Calendar Planner                           |    0 |     0 |      0 |    4 |     — | 0.000 |        — |
| s4       | `knowledge-searcher`        | lexiang-knowledge-base                     |    0 |     0 |      0 |    2 |     — | 0.000 |        — |
| s4       | `lead-generation`           | lead-generation                            |    7 |     7 |      0 |    1 | 1.000 | 0.875 |    1.000 |
| s4       | `offer-drafter`             | contract-review                            |    8 |     7 |      1 |    0 | 0.875 | 1.000 |    1.000 |
| s4       | `response-generator`        | email-writer                               |   10 |    10 |      0 |    0 | 1.000 | 1.000 |    1.000 |
| s4       | `satisfaction-survey`       | Employee Survey                            |    0 |     0 |      0 |    3 |     — | 0.000 |        — |
| s4       | `solution-recommender`      | contract-review-agent                      |    5 |     5 |      0 |    0 | 1.000 | 1.000 |    1.000 |

### 4.2 End-to-end cycle-discovery precision

**Setup.** We run the full three-stage pipeline (LLM I/O extraction → UDG
construction → cycle enumeration) end-to-end over all four scenarios and evaluate
the semantic activatability of the discovered candidate cycles (precision).

**Candidate enumeration.** Table I of the paper reports the UDG construction and
cycle-discovery results across the four scenarios: 67 skills, 243 action nodes,
1,865 retained edges, and 1,053 retained candidate cycles (obtained from 4,476 raw
simple cycles after rotation-based de-duplication):

| Scenario                | Skills | Actions |     Edges | Retained cycles |
| ----------------------- | -----: | ------: | --------: | --------------: |
| S1 Office Collaboration |     17 |      34 |       195 |             397 |
| S2 Content Creation     |     16 |     157 |     1,311 |             184 |
| S3 Data Analysis        |     19 |      36 |       282 |             361 |
| S4 Customer Service     |     15 |      16 |        77 |             111 |
| **Total**               | **67** | **243** | **1,865** |       **1,053** |

**Semantic validation of candidate cycles.** Three annotators independently
human-review the 1,053 candidate cycles to judge whether each forms a semantically
activatable closed loop (each skill's artifact is the next skill's working object,
closing back to the first). Each annotator labels every cycle against
a shared rubric — *activatable* if every edge in the loop forms a real data
dependency, *not activatable* otherwise. The final label per cycle is decided by
majority vote across the three annotators, with disagreements adjudicated through a
short consensus discussion. Because no exhaustive
ground-truth set of all activatable cycles is available, we report precision rather
than recall — the fraction of candidate cycles the annotators confirm as semantically
activatable:

| Scenario                | Retained cycles |   Valid | Precision |
| ----------------------- | --------------: | ------: | --------: |
| S1 Office Collaboration |             397 |     164 |     41.3% |
| S2 Content Creation     |             184 |      91 |     49.5% |
| S3 Data Analysis        |             361 |     116 |     32.1% |
| S4 Customer Service     |             111 |      61 |     55.0% |
| **Total**               |       **1,053** | **432** | **41.0%** |

Valid cycles are found in every scenario. Precision is highest in S4 (customer
service, 55.0%) and S2 (content creation, 49.5%), consistent with their shorter
average cycle length (3.6 and 3.9 hops in Table I), and lower in S1 (41.3%) and S3
(32.1%). The paper's case-study cycle (`Blog Writer` ↔ `content-writer` ↔
`seo-keyword-researcher`) is among the validated S2 cycles.

**Interpretation.** The pipeline shrinks the raw cycle space from 4,476 to 1,053
retained cycles, of which the annotators confirm 432 (41.0%) as semantically
activatable — demonstrating that the pipeline identifies a substantial set of
semantically activatable cycles across all four scenarios. Higher precision in S4 and
S2 coincides with their shorter average cycle lengths, although scenario-specific
factors may also contribute. These results show that SkillWeaver identifies
semantically activatable cross-skill loops across all four scenarios, a sampled
subset of which is subsequently evaluated for resource amplification in live execution.

---

## DATA-5 — Type Label & Name Identifier for Type Compatibility

In natural-language skill descriptions, the **type label** reflects form-level
compatibility of a parameter, while the **name identifier** supplies its semantic
role when the type alone is ambiguous. We quantify this with a controlled
experiment: we score a panel of signals against a human-annotated ground truth of
parameter-pair compatibility.

### 5.1 Setup

From the reviewed final I/O ground truth (67 skills) we form the full cross product
of **192 output × 297 input = 57,024 parameter pairs**. For each pair, **three
annotators** independently judge whether the output value can be passed directly as the input's
data (no transformation), based on parameter semantics; the final label is decided by
**majority vote** across the three annotators, as in DATA-4. We stratify a fixed-seed
sample of **501 pairs** over the six `type_band × name_band` strata and label it
under a shared guideline.

**Signals compared** — five generic baselines and the paper's three signals:

| Signal               | Definition                                    |
| -------------------- | --------------------------------------------- |
| `exact_type_match`   | 1 if the two type strings are equal, else 0   |
| `char_ngram_jaccard` | char 3-gram Jaccard over the names            |
| `levenshtein`        | normalized edit similarity over the names     |
| `tfidf_cosine`       | TF-IDF (1,2)-gram cosine over the names       |
| `word_jaccard`       | word-set Jaccard over tokenized names         |
| `type_score`         | the paper's hand-crafted type matrix          |
| `name_score`         | the paper's substring / word-in-name rule     |
| `compat`             | the paper's `0.6·type_score + 0.4·name_score` |

Each signal is scored against the binary label with **AUC** (primary) and **Spearman
rank correlation** (secondary).

### 5.2 Results

Across **501 pairs** (38 compatible / 463 incompatible, base rate 0.076):

| Signal               |       AUC | Spearman |
| -------------------- | --------: | -------: |
| `exact_type_match`   |     0.853 |   +0.400 |
| `char_ngram_jaccard` |     0.851 |   +0.381 |
| `levenshtein`        |     0.844 |   +0.315 |
| `tfidf_cosine`       |     0.575 |   +0.283 |
| `word_jaccard`       |     0.898 |   +0.499 |
| `type_score`         |     0.867 |   +0.362 |
| `name_score`         |     0.810 |   +0.335 |
| `compat`             | **0.933** |   +0.404 |

- **Individually discriminative.** `type_score` (AUC 0.867) exceeds the hard-equality
  baseline `exact_type_match` (0.853): a soft type matrix captures form compatibility
  that binary equality misses. `name_score` (AUC 0.810, ≫ 0.5) shows the name
  identifier carries real semantic-role information.
- **Combination achieves the highest AUC.** `compat = 0.6·type + 0.4·name` attains
  **AUC 0.933**, the highest of all eight signals — type filters irreconcilable *form*
  conflicts, name resolves *semantic-role* identity when the form alone is ambiguous.
- **TF-IDF similarity performs poorly on short parameter names.** `tfidf_cosine` collapses to 0.575
  (≈ random): a parameter name is a single short identifier, so word-level TF-IDF
  finds almost no shared vocabulary and its vectors are near-orthogonal — exactly why
  SkillWeaver uses *structured* type and name signals.
- **On `word_jaccard` > `name_score`.** `word_jaccard` (0.898) is itself a *name*
  signal, so its slightly higher AUC than the coarse three-valued `name_score`
  (0.810) reinforces — not contradicts — the value of the name identifier; refining
  `name_score` toward a continuous form is a future direction that changes no
  conclusion here.

### 5.3 Robustness to annotation aperture

A bare `content`/`text` input vs. a domain-specific output (`email_content`) admits
borderline labels. We re-score under two stricter apertures:

- **drop-annotator** (leave-one-annotator-out): re-score after removing one annotator
  at a time, scoring by the remaining annotators' agreement, to confirm the AUC does
  not hinge on any single annotator's judgment.
- **flip-generic**: re-score after flipping to *incompatible* every pair whose
  compatibility rested on a generic `content`/`text` type being accepted, to confirm
  the AUC does not hinge on the generic-type shortcut.

| Signal             | Full AUC | drop-annotator | flip-generic |
| ------------------ | -------: | -------------: | -----------: |
| `exact_type_match` |    0.853 |          0.819 |        0.829 |
| `word_jaccard`     |    0.898 |          0.891 |        0.869 |
| `type_score`       |    0.867 |          0.851 |        0.850 |
| `name_score`       |    0.810 |          0.825 |        0.788 |
| `compat`           |    0.933 |          0.925 |        0.911 |

The ordering is stable under every aperture: `compat` stays highest, `type_score`
stays above `exact_type_match`, and `name_score` stays well above chance.
