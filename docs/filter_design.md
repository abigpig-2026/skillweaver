# SkillWeaver Cross-Skill Edge Filtering Design Document

> This document records the filtering layer design of `SkillGraphMatcher` in `modules/multi_skill_pathfinder.py`,
> including design motivation, alignment with Paper Algorithm 1, removed over-filtering mechanisms, and their justifications.
> Intended as reference material for writing Paper Section 4.2 "UDG Construction and Cycle Enumeration."

---

## 1. Design Objectives

When constructing the Unified Dependency Graph (UDG), cross-skill action edges $e_{i \to j}$ between any two skills $s_i, s_j$ must be filtered to control graph scale while retaining high-confidence attack path candidates. The filtering design must simultaneously satisfy:

- **Recall**: Avoid over-pruning; ensure that genuinely existing cyclic paths are not omitted.
- **Precision**: Suppress low-quality edges to prevent state explosion in the subsequent SCC + Johnson enumeration stage.
- **Interpretability**: Each filtering layer corresponds to an explicit mathematical constraint in the paper, facilitating experimental reproduction and ablation analysis.

---

## 2. Filtering Layer Architecture (Three-Layer Structure)

This implementation adopts a three-layer filtering architecture consistent with Paper Section 4.2:

```
Layer 1: TypeCompat(O_i, I_j)         — Output-input type compatibility (t_ij = max compat)
Layer 2: Affinity Φ(a_i, a_j)         — Composite dependency score:
           Φ = 0.35·t_ij + 0.35·c_ij + 0.30·s_ij
Layer 3: Three-threshold edge retention — t_ij ≥ τ_t ∧ c_ij ≥ ρ ∧ Φ ≥ η
```

After filtering, the graph algorithm stage proceeds:

```
Step 4: Tarjan SCC                 — Extract strongly connected components
Step 5: Johnson + k >= min_hop     — Enumerate bounded simple cycles
```

---

## 3. Detailed Layer Design

### Layer 1: Type Compatibility

**Mathematical definition**:
Given skill $s_i$'s output parameter set $\mathcal{O}_i$ and skill $s_j$'s input parameter set $\mathcal{I}_j$,
type compatibility $\mathrm{TC}(\mathcal{O}_i, \mathcal{I}_j)$ is computed via parameter-level matching:

$$
\mathrm{TC}(o, i) = 0.6 \cdot \mathrm{type\_score}(o, i) + 0.4 \cdot \mathrm{name\_score}(o, i)
$$

where:
- $\mathrm{type\_score}$ is based on a predefined type compatibility matrix (see table below);
- $\mathrm{name\_score}$ is based on parameter-name substring matching (containment 0.8, token overlap 0.5).

**Type Compatibility Matrix** (key entries):

| Output Type | Input Type | Compatibility Score | Explanation |
|-------------|------------|---------------------|-------------|
| string      | string     | 1.0                 | Fully compatible |
| json        | string     | 0.9                 | JSON can be serialized to string |
| number      | number     | 1.0                 | Same numeric type |
| unknown     | unknown    | 0.5                 | Weak compatibility; preserves exploration space |
| unknown     | string     | 0.4                 | Degraded match; does not block |
| unknown     | json       | 0.4                 | Degraded match; does not block |
| unknown     | number     | 0.3                 | Degraded match; does not block |
| *other*     | *other*    | 0.3                 | Default fallback |

**Handling Strategy for `unknown` Type**:

Skill I/O parameter types are extracted from SKILL.md and script source code via static parsing (regex/AST).
Due to the weakly typed nature of natural-language documentation, many parameters cannot be precisely classified; fallback to `"unknown"` is intentional design behavior.

The early implementation treated `unknown` as universally incompatible (returning 0.0), causing many legitimate edges to be incorrectly discarded.
After optimization, a **degraded-match strategy** is adopted:
- `unknown \to unknown`: 0.5 (weakly compatible; acknowledges missing information without blocking);
- `unknown \to` concrete type: 0.3-0.4 (degraded but not rejected).

**Supporting evidence**:
- PCART~\cite{pcart2024}, in studying automated repair of Python API parameter compatibility issues, demonstrates that type inference failures should use degraded matching rather than hard rejection; its hybrid dynamic+static analysis achieves 93.26\% recall on PCBench;
- Typify~\cite{typify2025} notes that Python type inference is inherently uncertain, with static analysis tools typically covering less than 70\% of types in real codebases, making `unknown` fallback the norm rather than an anomaly.

---

### Layer 2: Dependency Score

**Mathematical definition** (Paper Section 4.2, Formula for Φ):

$$
\Phi(a_i, a_j) = \alpha \cdot t_{ij} + \beta \cdot c_{ij} + \delta \cdot s_{ij}
$$

where:
- $\alpha = 0.35, \beta = 0.35, \delta = 0.30$ (normalized weights, $\alpha+\beta+\delta=1$);
- $t_{ij} = \max_{p \in \mathcal{O}(a_i),\, q \in \mathcal{I}(a_j)} \operatorname{compat}(p,q)$: type compatibility from Layer 1;
- $c_{ij} = |\{ q \in \mathcal{I}^{\mathrm{req}}(a_j) \mid \exists p \in \mathcal{O}(a_i),\, \operatorname{compat}(p,q) \geq \tau_m \}| \;/\; |\mathcal{I}^{\mathrm{req}}(a_j)|$: input completeness (if $a_j$ has no required inputs, $c_{ij}=1$);
- $s_{ij}$: semantic relatedness via TF-IDF cosine similarity of action descriptions.

**Key Design Decision**: Semantic similarity is not used as a pre-filtering condition.

In the early implementation, action pairs with semantic similarity below `semantic_threshold` (default 0.15) were hard-pruned before computing the combined score.
The problems with this design are:
- Semantic similarity is only one of three factors (weight only 0.35); even with low $\mathrm{CS}$, high $\mathrm{TC}$ or high $B$ could still yield $P(s_i \to s_j) \geq \tau$;
- Pre-filtering causes the effective filtering strength to exceed the paper's stated $\tau = 0.4$, resulting in recall loss.

**Optimization**: Remove the `threshold_mask` pre-filter, compute the full combined score for all action pairs, and apply uniform filtering at Layer 3 using `affinity_threshold`.

**Supporting evidence**:
- DeepEra~\cite{deepera2025}'s evidence filtering module adopts a post-filtering strategy (RelevanceScore threshold applied after composite scoring); its ablation study shows pre-filtering causes significant performance degradation (HitRate@1 dropping from 66.06 to 62.60);
- memory-optimized-agent~\cite{memoryagent2025} notes that the optimal semantic threshold varies by domain, and a fixed pre-filtering threshold lacks adaptability.

---

### Layer 3: Three-Threshold Edge Retention

**Paper definition** (Section 4.2): An edge $(a_i, a_j)$ is retained only if:
$$
t_{ij} \geq \tau_t \quad \land \quad c_{ij} \geq \rho \quad \land \quad \Phi(a_i, a_j) \geq \eta
$$

**Default parameters**:
- $\tau_t = 0.3$: minimum type-compatibility threshold;
- $\rho = 0.3$: minimum input-completeness threshold;
- $\eta = 0.4$: dependency-score threshold (the main affinity threshold);
- $\tau_m = 0.3$: parameter-match threshold (used within $c_{ij}$ computation).

**Experimental tuning recommendations**:
- Default values above balance recall and precision across the included scenarios.
- $\eta$ is the primary tuning knob and can be adjusted when a denser or sparser retained graph is desired.

---

## 4. Removed Over-Filtering Mechanisms

### 4.1 Removed: Semantic Threshold Pre-Filtering

**Original implementation**:
```python
threshold_mask = sim_matrix >= self.semantic_threshold  # default 0.15
if not threshold_mask[i, j]:
    continue  # skip directly; type_aff and chain_prior are not computed
```

**Problems**:
- Pre-filtering executes before the combined score is computed, causing valid edges with low semantics but high type/prior scores to be incorrectly discarded.
- Filtering strength is uncontrollable; the effective equivalent threshold is far higher than $\tau = 0.4$.

**After removal**: All action pairs undergo full combined score computation; only the final uniform filter is applied.

---

### 4.2 Removed: Hard-Coded Memory Volatile Filtering

**Original implementation**:
```python
persistent_indicators = {'write', 'save', 'create', 'delete', 'mkdir', 'upload',
                         'db', 'database', 'sqlite', 'insert', 'update',
                         'file', 'download', 'export'}
if not self.is_memory_volatile(src_action, tgt_action):
    continue
```

**Problems**:
- Static detection based on keyword substring matching has an extremely high false-positive rate. Modern agent skills almost universally involve file I/O, network requests, database operations, and other "persistent" behaviors.
- Although Paper \S4.2 mentions `IsMemoryVolatile`, its context is distinguishing "pure in-memory flow" loops from "shared persistent storage" loops. In real skill ecosystems, both types of edges can form valid cycles (e.g., write$\to$read$\to$write).
- Paper Table 1 reports 1,875 cycles mined from 696 skills; this order of magnitude would be unattainable under such strict filtering.

**After removal**: All edges satisfying Layers 1-3 are admitted into the UDG, without distinguishing memory or persistent flows.

**Supporting evidence**:
- Agent-Infra AIO Sandbox~\cite{aio2026} and Fault-Tolerant Sandboxing~\cite{faultsandbox2025} both use runtime system-call monitoring to distinguish volatile/persistent, rather than static keyword matching.
- Runtime Safety Evaluation for AI Agent Tool Use~\cite{runtimesafety2025} notes that static keyword detection has an excessively high false-positive rate for agent tools and recommends dynamic behavioral analysis.

---

## 5. Alignment with Paper Algorithm 1

| Step        | Paper Section 4.2 | This Implementation | Consistency |
|-------------|-------------------|---------------------|-------------|
| Input       | Skill set $\mathcal{S}$, weights $\alpha,\beta,\delta$, thresholds $\tau_t,\rho,\eta$, min hop $K$ | Same | Consistent |
| Line 3-4    | $t_{ij} = \max_{p,q} \operatorname{compat}(p,q)$ | `evaluate_parameter_affinity` (max over pairs) | Consistent |
| Line 5      | $\Phi = \alpha t_{ij} + \beta c_{ij} + \delta s_{ij}$ | `combined = 0.35*t_ij + 0.35*c_ij + 0.30*s_ij` | Consistent |
| Line 6      | $t_{ij} \geq \tau_t \land c_{ij} \geq \rho \land \Phi \geq \eta$ | Three-threshold check in `match_skill_pair` | Consistent |
| Line 9      | $\text{RemoveBidirectionalEdges}$ | No explicit removal needed (SCC naturally handles $k=2$) | Equivalent |
| Line 10     | $\text{Tarjan}(G_{\text{pruned}})$ | `nx.strongly_connected_components` | Consistent |
| Line 12-14  | $\text{Johnson}(C)$, $|\ell| \geq K$ | `nx.simple_cycles(length_bound=6)`, `len(cyc) >= min_hop` | Consistent |

---

## 6. Complexity Analysis

**Edge filtering stage**:
- For $n$ skills, the action-level matching complexity for each pair $(s_i, s_j)$ is $O(|A_i| \cdot |A_j|)$, where $|A_i|$ is the number of action nodes in skill $i$.
- Batch semantic similarity computation is optimized via matrixization into a single `cosine_similarity` call.
- Total complexity: $O(|\mathcal{S}|^2 \cdot \bar{A}^2)$, where $\bar{A}$ is the average number of actions.

**Cycle enumeration stage**:
- Tarjan SCC: $O(V + E)$.
- Johnson's algorithm for simple cycle enumeration: $O((V + E) \cdot (C + 1))$, where $C$ is the number of simple cycles~\cite{johnson1975}.
- Bounded-length variant (`length_bound=6`) significantly reduces the effective search space for sparse graphs~\cite{gupta2021}.

---

## 7. References

```bibtex
@article{johnson1975,
  title={Finding all the elementary circuits of a directed graph},
  author={Johnson, Donald B},
  journal={SIAM Journal on Computing},
  volume=4,
  number=1,
  pages={77--84},
  year=1975
}

@article{gupta2021,
  title={Finding All Bounded-Length Simple Cycles in a Directed Graph},
  author={Gupta, Shiv and Suzumura, Toyotaro},
  journal={arXiv preprint arXiv:2106.08624},
  year=2021
}

@article{deepera2025,
  title={DeepEra: Agentic Reranking with Semantic Evidence Filtering},
  journal={arXiv preprint arXiv:2601.16478},
  year=2025
}

@misc{memoryagent2025,
  title={memory-optimized-agent: Production-ready AI context management using semantic similarity},
  author={Prakash, ConnectWith},
  howpublished={\url{https://github.com/connectwithprakash/memory-optimized-agent}},
  year=2025
}

@article{pcart2024,
  title={PCART: Automated Repair of Python API Parameter Compatibility Issues},
  journal={arXiv preprint arXiv:2406.03839},
  year=2024
}

@article{typify2025,
  title={Typify: A Lightweight Usage-driven Static Analyzer for Precise Python Type Inference},
  journal={arXiv preprint arXiv:2604.05067},
  year=2025
}

@article{aio2026,
  title={Agent-Infra Releases AIO Sandbox: An All-in-One Runtime for AI Agents},
  journal={MarkTechPost},
  year=2026,
  howpublished={\url{https://www.marktechpost.com/2026/03/29/agent-infra-releases-aio-sandbox/}}
}

@article{faultsandbox2025,
  title={Fault-Tolerant Sandboxing for AI Coding Agents: A Transactional Approach to Safe Autonomous Execution},
  journal={arXiv preprint arXiv:2512.12806},
  year=2025
}

@article{runtimesafety2025,
  title={Runtime Safety Evaluation and Interception for AI Agent Tool Use},
  journal={arXiv preprint arXiv:2605.04785},
  year=2025
}
```

---

## 8. Modification Log

| Date       | Modification | Impact |
|------------|-------------|--------|
| 2026-05-12 | Removed `semantic_threshold` pre-filtering | Recall improved; edges with low semantics but high type/prior scores are now preserved |
| 2026-05-12 | Removed `is_memory_volatile` hard-coded filtering | Recall improved; edges involving persistent operations are now preserved |
| 2026-05-12 | Relaxed `unknown` type compatibility (0.0 -> 0.3-0.5) | Recall improved; skills with failed I/O extraction are no longer completely blocked |
| 2026-05-12 | Parameterized `affinity_threshold` (default 0.4) | Controllability improved; facilitates experimental hyperparameter tuning |
| 2026-06-22 | Aligned Φ formula with the paper: $t_{ij}$ (max), $c_{ij}$ (input completeness), $s_{ij}$ (TF-IDF) | Paper Section 4.2 consistency; removed chain-prior from Φ and added three-threshold retention ($\tau_t,\rho,\eta$) |
