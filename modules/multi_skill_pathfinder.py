"""
Stage 2: UDG Construction and Cycle Enumeration (corresponding to Paper Section 4.2)

Constructs the Unified Dependency Graph (UDG) and enumerates cross-skill closed cycles.
Corresponds to Paper Section 4.2:

Dependency Score:
  Φ(a_i, a_j) = α·t_ij + β·c_ij + δ·s_ij
  where t_ij = type compatibility, c_ij = input completeness, s_ij = semantic relatedness
  (α=0.35, β=0.35, δ=0.30)

Edge Retention (three independent thresholds):
  t_ij ≥ τ_t  ∧  c_ij ≥ ρ  ∧  Φ(a_i, a_j) ≥ η

Construction pipeline:
1. Independently build a sub-graph for each skill (extract action nodes)
2. Compute pairwise action dependency scores via three-signal formula
3. Retain edges satisfying all three threshold conditions
4. Build the global weighted directed graph G = (V, E, w)
5. Enumerate bounded simple cycles via Tarjan SCC + Johnson's algorithm

Security notice: This code is intended solely for security research and red-team testing.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import gc
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import time
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .skill_graph_builder import SkillNode, SkillGraphBuilder, CommandChain


@dataclass
class ActionNode:
    """Action constraint tuple node -- T_i = <I_i, O_i, C_i, V_i>"""
    action_id: str
    parent_skill_id: str
    parent_skill_name: str
    command_chain: CommandChain
    inputs: List
    outputs: List
    semantic_vector: Optional[np.ndarray] = None
    description: str = ""


@dataclass
class SkillSubGraph:
    """Sub-graph of a single skill."""
    skill_id: str
    skill_name: str
    action_nodes: Dict[str, ActionNode] = field(default_factory=dict)
    internal_edges: List[Tuple[str, str]] = field(default_factory=list)  # edges between internal actions


@dataclass
class DirectedEdge:
    """Global directed edge e_{i→j} (cross-skill action transition)."""
    source_action_id: str
    target_action_id: str
    source_skill_id: str
    target_skill_id: str
    affinity_score: float
    semantic_similarity: float
    type_compatibility: float
    input_completeness: float = 0.0
    chain_flow_prior: float = 0.0
    parameter_flow: List[Tuple[str, str]] = field(default_factory=list)

    def __hash__(self):
        return hash((self.source_action_id, self.target_action_id))


@dataclass
class CyclicPath:
    """Cyclic attack path."""
    path_action_ids: List[str]
    path_skill_ids: List[str]
    path_skill_names: List[str]
    path_edges: List[DirectedEdge]
    hop_count: int
    total_affinity: float
    avg_semantic_sim: float
    
    def __hash__(self):
        cycle_key = tuple(sorted(self.path_action_ids))
        return hash(cycle_key)
    
    def __eq__(self, other):
        if not isinstance(other, CyclicPath):
            return False
        return set(self.path_action_ids) == set(other.path_action_ids)


class SkillGraphMatcher:
    """Pairwise Skill sub-graph matcher.

    Computes connectivity between two skill sub-graphs, corresponding to
    Paper Section 4.2 formulas:

    Dependency Score:
      Φ(a_i, a_j) = α·t_ij + β·c_ij + δ·s_ij
      (α=0.35, β=0.35, δ=0.30)

    where:
    - t_ij = max_{p,q} compat(p,q): type compatibility (max over parameter pairs)
    - c_ij = |{q in I_req(a_j) | ∃p, compat(p,q) ≥ τ_m}| / |I_req(a_j)|: input completeness
    - s_ij: semantic relatedness (cosine similarity of TF-IDF vectors)

    Edge Retention (Paper Equation):
      t_ij ≥ τ_t  ∧  c_ij ≥ ρ  ∧  Φ(a_i, a_j) ≥ η

    where τ_t, ρ, η are configurable thresholds.
    """

    def __init__(self, tau_m: float = 0.3, tau_t: float = 0.3,
                 rho: float = 0.3, eta: float = 0.4):
        self.tau_m = tau_m   # parameter-match threshold for c_ij computation
        self.tau_t = tau_t   # minimum type-compatibility threshold
        self.rho = rho       # minimum input-completeness threshold
        self.eta = eta       # dependency-score threshold

        self.type_compatibility = {
            ('string', 'string'): 1.0, ('string', 'json'): 0.8, ('string', 'url'): 0.7,
            ('string', 'file'): 0.6, ('json', 'string'): 0.9, ('json', 'json'): 1.0,
            ('number', 'string'): 0.8, ('number', 'number'): 1.0, ('boolean', 'boolean'): 1.0,
            ('boolean', 'string'): 0.7, ('url', 'string'): 0.9, ('url', 'url'): 1.0,
            ('file', 'string'): 0.8, ('file', 'file'): 1.0,
            ('unknown', 'unknown'): 0.5,
            ('unknown', 'string'): 0.4, ('string', 'unknown'): 0.4,
            ('unknown', 'json'): 0.4, ('json', 'unknown'): 0.4,
            ('unknown', 'number'): 0.3, ('number', 'unknown'): 0.3,
        }

        self.chain_flow_patterns = {
            ('list', 'get'): 0.9, ('list', 'view'): 0.9,
            ('snapshot', 'click'): 0.9, ('snapshot', 'fill'): 0.9,
            ('snapshot', 'type'): 0.9, ('snapshot', 'get'): 0.85,
            ('open', 'snapshot'): 0.8, ('open', 'get'): 0.6,
            ('search', 'read'): 0.8, ('read', 'analyze'): 0.85,
            ('read', 'process'): 0.8, ('search', 'fetch'): 0.75,
            ('fetch', 'parse'): 0.85, ('parse', 'analyze'): 0.9,
            ('analyze', 'summarize'): 0.9, ('analyze', 'report'): 0.85,
            ('generate', 'send'): 0.8, ('process', 'write'): 0.75,
            ('get', 'click'): 0.5, ('get', 'open'): 0.4,
            ('api', 'get'): 0.7, ('find', 'read'): 0.8,
        }

    def compute_type_compatibility(self, output_type: str, input_type: str) -> float:
        """Compute output-input type compatibility.

        "unknown" denotes a fallback marker for failed IO extraction.
        A downgrade matching strategy is adopted:
        - unknown→unknown: 0.5 (weak compatibility, preserving exploration space)
        - unknown→concrete type: 0.3-0.4 (downgraded but not blocked)
        This avoids returning 0.0 uniformly, which would falsely eliminate many legitimate edges.
        """
        out_t = output_type.lower().strip()
        in_t = input_type.lower().strip()
        key = (out_t, in_t)
        if key in self.type_compatibility:
            return self.type_compatibility[key]
        # Fallback downgrade for single-sided unknown
        if out_t == 'unknown' or in_t == 'unknown':
            return 0.3
        return 0.3

    def compute_chain_flow_prior(self, src_action: ActionNode, tgt_action: ActionNode) -> float:
        src_sub = src_action.command_chain.subcommand.lower()
        tgt_sub = tgt_action.command_chain.subcommand.lower()
        flow_key = (src_sub, tgt_sub)
        if flow_key in self.chain_flow_patterns:
            return self.chain_flow_patterns[flow_key]
        if src_action.command_chain.tool == tgt_action.command_chain.tool:
            if src_action.command_chain.tool in ['agent-browser', 'gh']:
                return 0.5
        return 0.15

    def evaluate_parameter_affinity(self, src: ActionNode, tgt: ActionNode) -> Tuple[float, List[Tuple[str, str]]]:
        """Compute t_ij = max_{p in O(a_i), q in I(a_j)} compat(p, q).

        Paper formula: t_ij = max_{p,q} compat(p,q), where compat(p,q) ∈ [0,1]
        is computed from type consistency and name similarity.
        """
        if not src.outputs or not tgt.inputs:
            return 0.0, []

        best_overall_score = 0.0
        best_pair = None

        for out_param in src.outputs:
            for in_param in tgt.inputs:
                type_score = self.compute_type_compatibility(
                    (out_param.get('type', 'unknown') if isinstance(out_param, dict) else getattr(out_param, 'param_type', 'unknown')),
                    (in_param.get('type', 'unknown') if isinstance(in_param, dict) else getattr(in_param, 'param_type', 'unknown'))
                )
                name_score = 0.0
                out_name = (out_param.get('name', '') if isinstance(out_param, dict) else getattr(out_param, 'name', '')).lower()
                in_name = (in_param.get('name', '') if isinstance(in_param, dict) else getattr(in_param, 'name', '')).lower()
                if out_name in in_name or in_name in out_name:
                    name_score = 0.8
                elif any(word in out_name for word in in_name.split()):
                    name_score = 0.5
                score = type_score * 0.6 + name_score * 0.4
                if score > best_overall_score:
                    best_overall_score = score
                    best_pair = (
                        out_param.get('name', '') if isinstance(out_param, dict) else getattr(out_param, 'name', ''),
                        in_param.get('name', '') if isinstance(in_param, dict) else getattr(in_param, 'name', ''),
                    )

        param_flow = [best_pair] if best_pair and best_overall_score > 0.3 else []
        return best_overall_score, param_flow

    def compute_input_completeness(self, src: ActionNode, tgt: ActionNode) -> float:
        """Compute c_ij = |{q in I_req(a_j) | exists p in O(a_i), compat(p,q) >= tau_m}| / |I_req(a_j)|.

        Paper formula: input completeness measures the fraction of required inputs of
        a_j that can be matched by outputs of a_i. If a_j has no required inputs, c_ij = 1.
        """
        required_inputs = [inp for inp in tgt.inputs if (inp.get('required', True) if isinstance(inp, dict) else getattr(inp, 'required', True))]
        if not required_inputs:
            return 1.0

        matched = 0
        for req_in in required_inputs:
            for out_param in src.outputs:
                type_score = self.compute_type_compatibility(
                    (out_param.get('type', 'unknown') if isinstance(out_param, dict) else getattr(out_param, 'param_type', 'unknown')),
                    (req_in.get('type', 'unknown') if isinstance(req_in, dict) else getattr(req_in, 'param_type', 'unknown'))
                )
                name_score = 0.0
                out_name = (out_param.get('name', '') if isinstance(out_param, dict) else getattr(out_param, 'name', '')).lower()
                in_name = (req_in.get('name', '') if isinstance(req_in, dict) else getattr(req_in, 'name', '')).lower()
                if out_name in in_name or in_name in out_name:
                    name_score = 0.8
                elif any(word in out_name for word in in_name.split()):
                    name_score = 0.5
                compat = type_score * 0.6 + name_score * 0.4
                if compat >= self.tau_m:
                    matched += 1
                    break

        return matched / len(required_inputs)

    def match_skill_pair(self, src_skill: SkillSubGraph, tgt_skill: SkillSubGraph) -> List[DirectedEdge]:
        """Compute all connected edges between two skill sub-graphs.

        Filtering pipeline (Paper Section 4.2):
        1. Batch computation of semantic similarity matrix (no pre-filtering)
        2. Compute t_ij (type compatibility) via evaluate_parameter_affinity (max over pairs)
        3. Compute c_ij (input completeness) via compute_input_completeness
        4. Compute s_ij (semantic relatedness) via TF-IDF cosine similarity
        5. Φ(a_i, a_j) = 0.35·t_ij + 0.35·c_ij + 0.30·s_ij
        6. Edge retained iff: t_ij ≥ τ_t  ∧  c_ij ≥ ρ  ∧  Φ ≥ η
        """
        edges = []

        # Precompute semantic vectors (support both TF-IDF vectors and legacy semantic_vector)
        src_vecs = {}
        tgt_vecs = {}
        for src_id, src_action in src_skill.action_nodes.items():
            # Prefer tfidf_vector (new structure); otherwise use semantic_vector (legacy)
            vec = getattr(src_action, 'tfidf_vector', None)
            if vec is None:
                vec = getattr(src_action, 'semantic_vector', None)
            if vec is not None:
                src_vecs[src_id] = vec.reshape(1, -1)
        for tgt_id, tgt_action in tgt_skill.action_nodes.items():
            vec = getattr(tgt_action, 'tfidf_vector', None)
            if vec is None:
                vec = getattr(tgt_action, 'semantic_vector', None)
            if vec is not None:
                tgt_vecs[tgt_id] = vec.reshape(1, -1)

        # If either skill has no valid vectors, skip the semantic dimension but still compute type+prior
        has_semantic = bool(src_vecs and tgt_vecs)
        if has_semantic:
            src_ids = list(src_vecs.keys())
            tgt_ids = list(tgt_vecs.keys())
            src_matrix = np.vstack([src_vecs[sid] for sid in src_ids])
            tgt_matrix = np.vstack([tgt_vecs[tid] for tid in tgt_ids])
            sim_matrix = cosine_similarity(src_matrix, tgt_matrix)
        else:
            src_ids = list(src_skill.action_nodes.keys())
            tgt_ids = list(tgt_skill.action_nodes.keys())
            sim_matrix = None

        for i, src_id in enumerate(src_ids):
            src_action = src_skill.action_nodes[src_id]
            for j, tgt_id in enumerate(tgt_ids):
                tgt_action = tgt_skill.action_nodes[tgt_id]

                type_aff, param_flow = self.evaluate_parameter_affinity(src_action, tgt_action)
                if type_aff <= 0:
                    continue

                if has_semantic:
                    sem_sim = float(sim_matrix[i, j])
                else:
                    sem_sim = 0.0

                # Compute c_ij (input completeness) — Paper Section 4.2
                input_comp = self.compute_input_completeness(src_action, tgt_action)

                # Φ(a_i, a_j) = α·t_ij + β·c_ij + δ·s_ij  (α=0.35, β=0.35, δ=0.30)
                combined = 0.35 * type_aff + 0.35 * input_comp + 0.30 * max(0, sem_sim)

                # Three-threshold edge retention — Paper Equation
                if type_aff >= self.tau_t and input_comp >= self.rho and combined >= self.eta:
                    edge = DirectedEdge(
                        source_action_id=src_id,
                        target_action_id=tgt_id,
                        source_skill_id=src_skill.skill_id,
                        target_skill_id=tgt_skill.skill_id,
                        affinity_score=combined,
                        semantic_similarity=sem_sim,
                        type_compatibility=type_aff,
                        input_completeness=input_comp,
                        chain_flow_prior=0.0,
                        parameter_flow=param_flow
                    )
                    edges.append(edge)

        return edges


class UDGBuilder:
    """Unified Dependency Graph (UDG) builder -- build per-skill sub-graphs first, then perform pairwise matching.

    Pipeline:
    1. Independently build a sub-graph for each skill (extract action nodes)
    2. Pairwise skill sub-graph matching; compute cross-skill connecting edges
    3. Build the global weighted directed graph
    """
    
    def __init__(self, tau_m: float = 0.3, tau_t: float = 0.3,
                 rho: float = 0.3, eta: float = 0.4,
                 affinity_threshold: Optional[float] = None):
        # Backward compatibility: if affinity_threshold is passed, use it as eta
        if affinity_threshold is not None:
            eta = affinity_threshold
        self.skill_nodes: Dict[str, SkillNode] = {}
        self.skill_subgraphs: Dict[str, SkillSubGraph] = {}
        self.global_action_nodes: Dict[str, ActionNode] = {}
        self.global_edges: Dict[Tuple[str, str], DirectedEdge] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        self.tau_m = tau_m
        self.tau_t = tau_t
        self.rho = rho
        self.eta = eta
        self.scc_list: List[Set[str]] = []
        self.matcher = SkillGraphMatcher(tau_m=tau_m, tau_t=tau_t, rho=rho, eta=eta)
    
    def add_skill_node(self, node: SkillNode):
        self.skill_nodes[node.skill_id] = node
    
    def add_nodes_from_builder(self, builder: SkillGraphBuilder):
        for skill_id, node in builder.get_all_nodes().items():
            self.add_skill_node(node)
        print(f"[INFO] UDG: imported {len(self.skill_nodes)} skill nodes")
    
    def build_skill_subgraphs(self) -> Dict[str, SkillSubGraph]:
        """Stage 1: Independently build a sub-graph for each skill.

        As required by the paper, extract independent IO constraints and TF-IDF
        vectors for each action node.
        """
        print(f"[INFO] UDG: beginning independent sub-graph construction for each skill...")
        
        for skill_id, skill in self.skill_nodes.items():
            subgraph = SkillSubGraph(skill_id=skill_id, skill_name=skill.name)
            
            # If SkillNode has the actions field (new structure), use it directly
            if hasattr(skill, 'actions') and skill.actions:
                for action in skill.actions:
                    # Action nodes already contain independent IO and TF-IDF vectors
                    subgraph.action_nodes[action.action_id] = action
                    self.global_action_nodes[action.action_id] = action
            else:
                # Legacy compatibility: create action nodes from command_chains
                if skill.command_chains:
                    for idx, chain in enumerate(skill.command_chains):
                        action_id = f"{skill_id}_action_{idx}"
                        action = ActionNode(
                            action_id=action_id,
                            parent_skill_id=skill_id,
                            parent_skill_name=skill.name,
                            command_chain=chain,
                            inputs=[{"name": i.name, "type": i.param_type} for i in skill.inputs],
                            outputs=[{"name": o.name, "type": o.param_type} for o in skill.outputs],
                            semantic_vector=skill.semantic_vector,
                            description=chain.description or f"{skill.name}: {chain.tool} {chain.subcommand}"
                        )
                        subgraph.action_nodes[action_id] = action
                        self.global_action_nodes[action_id] = action
                else:
                    action_id = f"{skill_id}_action_0"
                    action = ActionNode(
                        action_id=action_id,
                        parent_skill_id=skill_id,
                        parent_skill_name=skill.name,
                        command_chain=CommandChain(
                            tool="unknown", subcommand="", action="",
                            description=skill.description
                        ),
                        inputs=[{"name": i.name, "type": i.param_type} for i in skill.inputs],
                        outputs=[{"name": o.name, "type": o.param_type} for o in skill.outputs],
                        semantic_vector=skill.semantic_vector,
                        description=skill.description
                    )
                    subgraph.action_nodes[action_id] = action
                    self.global_action_nodes[action_id] = action
            
            self.skill_subgraphs[skill_id] = subgraph
        
        total_actions = sum(len(sg.action_nodes) for sg in self.skill_subgraphs.values())
        print(f"[INFO] UDG: built {len(self.skill_subgraphs)} skill sub-graphs, "
              f"{total_actions} action nodes in total")
        
        return self.skill_subgraphs
    
    def match_all_skill_pairs(self) -> int:
        """Stage 2: Pairwise skill sub-graph matching; build the global graph."""
        
        skill_ids = list(self.skill_subgraphs.keys())
        total_pairs = len(skill_ids) * (len(skill_ids) - 1)  # excluding i==j cases
        
        print(f"[INFO] UDG: beginning pairwise skill sub-graph matching ({total_pairs} pairs total)...")
        
        edge_count = 0
        connected_pair_count = 0
        checked_pairs = 0
        
        from tqdm import tqdm
        with tqdm(total=total_pairs, desc="  Matching progress", unit="pairs") as pbar:
            for i in range(len(skill_ids)):
                for j in range(len(skill_ids)):
                    if i == j:
                        continue
                    
                    checked_pairs += 1
                    src_sg = self.skill_subgraphs[skill_ids[i]]
                    tgt_sg = self.skill_subgraphs[skill_ids[j]]
                    
                    if src_sg.action_nodes and tgt_sg.action_nodes:
                        edges = self.matcher.match_skill_pair(src_sg, tgt_sg)
                        
                        if edges:
                            connected_pair_count += 1
                        
                        for edge in edges:
                            key = (edge.source_action_id, edge.target_action_id)
                            self.global_edges[key] = edge
                            self.adjacency[edge.source_action_id].append(edge.target_action_id)
                            edge_count += 1
                    
                    pbar.update(1)
                    pbar.set_postfix({'edges': edge_count, 'connected': connected_pair_count})
        
        print(f"[INFO] UDG: pairwise matching complete; {total_pairs} skill pairs checked, "
              f"{connected_pair_count} pairs produced connections, "
              f"{edge_count} action-level directed edges in total")
        
        return edge_count
    
    def _tarjan_scc(self) -> List[Set[str]]:
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []
        
        def strongconnect(v):
            index[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack[v] = True
            
            for w in self.adjacency.get(v, []):
                if w not in index:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack.get(w, False):
                    lowlinks[v] = min(lowlinks[v], index[w])
            
            if lowlinks[v] == index[v]:
                scc = set()
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.add(w)
                    if w == v:
                        break
                sccs.append(scc)
        
        for v in self.global_action_nodes:
            if v not in index:
                strongconnect(v)
        
        return sccs
    
    def _find_simple_cycles_johnson(self, scc: Set[str], min_hop: int) -> List[List[str]]:
        scc_nodes = sorted(list(scc))
        if len(scc_nodes) < min_hop:
            return []
        
        cycles = []
        sub_adj = {}
        for node in scc_nodes:
            sub_adj[node] = [n for n in self.adjacency.get(node, []) if n in scc]
        
        for i, start in enumerate(scc_nodes):
            candidates = set(scc_nodes[i:])
            self._johnson_dfs(start, start, [start], {start}, sub_adj, candidates, cycles, min_hop)
        
        unique = []
        seen = set()
        for cycle in cycles:
            if len(cycle) >= min_hop:
                min_idx = cycle.index(min(cycle))
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                if normalized not in seen:
                    seen.add(normalized)
                    unique.append(cycle)
        
        return unique
    
    def _johnson_dfs(self, start, current, path, visited, sub_adj, candidates, cycles, min_hop):
        if len(path) >= 12:
            return
        for neighbor in sub_adj.get(current, []):
            if neighbor == start and len(path) >= min_hop:
                cycles.append(path + [start])
            elif neighbor not in visited and neighbor in candidates:
                visited.add(neighbor)
                path.append(neighbor)
                self._johnson_dfs(start, neighbor, path, visited, sub_adj, candidates, cycles, min_hop)
                path.pop()
                visited.remove(neighbor)
    
    def export_udg(self, output_path: str):
        udg_data = {
            'skill_subgraphs': {
                sid: {
                    'skill_name': sg.skill_name,
                    'action_count': len(sg.action_nodes),
                    'actions': [
                        {
                            'id': aid,
                            'command': f"{a.command_chain.tool} {a.command_chain.subcommand} {a.command_chain.action}",
                            'description': a.description[:100]
                        }
                        for aid, a in sg.action_nodes.items()
                    ]
                }
                for sid, sg in self.skill_subgraphs.items()
            },
            'global_edges_count': len(self.global_edges),
            'metadata': {
                'skill_count': len(self.skill_nodes),
                'action_count': len(self.global_action_nodes),
                'edge_count': len(self.global_edges),
                'tau_m': self.tau_m,
                'tau_t': self.tau_t,
                'rho': self.rho,
                'eta': self.eta
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(udg_data, f, indent=2, ensure_ascii=False)
        
        print(f"[INFO] UDG graph exported: {output_path}")


class MultiSkillPathfinder:
    """Multi-skill path finder.

    Pipeline:
    1. Independently build a sub-graph for each skill
    2. Pairwise skill sub-graph matching; combine each pair (A, B) into a sub-graph
    3. Find cycles on each combined graph of pair (A, B) (cycles contain only A and B action nodes)
    4. Collect cyclic paths across all skill pairs
    """
    
    def __init__(self, udg: UDGBuilder, min_hop: int = 3, 
                 enable_illusion: bool = True, enable_entropy: bool = True):
        self.udg = udg
        self.min_hop = min_hop
        self.enable_illusion = enable_illusion  # progress-illusion mechanism
        self.enable_entropy = enable_entropy    # dynamic entropy injection
        self.cyclic_paths: List[CyclicPath] = []
    
    def _find_cycles_in_pair(self, skill_a: str, skill_b: str, max_cycles_per_pair: int = 5) -> List[List[str]]:
        """Find cycles on the combined graph of two skills.

        1. Extract all action edges between A and B (A→B and B→A)
        2. Build the combined graph
        3. Use DFS to find simple cycles with at least min_hop hops
        4. Limit the number of cycles returned to ensure diversity
        """
        # Collect edges between A↔B
        edges_a_to_b = []
        edges_b_to_a = []
        
        for (src, tgt), edge in self.udg.global_edges.items():
            if edge.source_skill_id == skill_a and edge.target_skill_id == skill_b:
                edges_a_to_b.append(edge)
            elif edge.source_skill_id == skill_b and edge.target_skill_id == skill_a:
                edges_b_to_a.append(edge)
        
        # If either direction has no edges, a cross-skill cycle cannot form
        if not edges_a_to_b or not edges_b_to_a:
            return []
        
        # Build adjacency list for the combined graph (only A and B action nodes)
        adjacency = defaultdict(list)
        for edge in edges_a_to_b + edges_b_to_a:
            adjacency[edge.source_action_id].append((edge.target_action_id, edge))
        
        # DFS to find cycles
        cycles = []
        all_nodes = list(adjacency.keys())
        
        for start_node in all_nodes:
            self._pair_dfs(start_node, start_node, [start_node], {start_node}, adjacency, cycles)
            
            # Early exit once enough cycles have been found
            if len(cycles) >= max_cycles_per_pair * 3:
                break
        
        # Deduplicate
        unique = []
        seen = set()
        for cycle in cycles:
            if len(cycle) >= self.min_hop:
                min_idx = cycle.index(min(cycle))
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                if normalized not in seen:
                    seen.add(normalized)
                    unique.append(cycle)
                    
                    # Limit the number returned
                    if len(unique) >= max_cycles_per_pair:
                        break
        
        return unique
    
    def _pair_dfs(self, start, current, path, visited, adjacency, cycles, max_depth=6):
        """DFS on the combined graph of two skills to find cycles (iterative version, to avoid recursive stack overflow)."""
        # Use iterative DFS instead of recursion to avoid stack overflow
        stack = [(start, current, list(path), set(visited))]
        
        while stack:
            # More aggressive stack size limit
            if len(stack) > 5000:
                # Truncate the stack; keep the first 3000
                stack = stack[:3000]
            
            s, c, p, v = stack.pop()
            
            # Limit search depth
            if len(p) > max_depth:
                continue
            
            for neighbor, edge in adjacency.get(c, []):
                if neighbor == s and len(p) >= self.min_hop:
                    cycles.append(p + [s])
                    # Limit the cycle count to prevent memory explosion
                    if len(cycles) > 100:
                        return
                elif neighbor not in v:
                    new_v = v | {neighbor}
                    new_p = p + [neighbor]
                    stack.append((s, neighbor, new_p, new_v))
    
    def _resolve_action_path_for_pair(self, cycle: List[str], skill_a: str, skill_b: str) -> Optional[CyclicPath]:
        """Resolve an action-level cycle into a CyclicPath object."""
        edges = []
        total_aff = 0.0
        total_sem = 0.0
        
        for i in range(len(cycle)):
            src = cycle[i]
            tgt = cycle[(i + 1) % len(cycle)]
            edge = self.udg.global_edges.get((src, tgt))
            if edge:
                edges.append(edge)
                total_aff += edge.affinity_score
                total_sem += edge.semantic_similarity
        
        if not edges:
            return None
        
        skill_ids = [self.udg.global_action_nodes[n].parent_skill_id for n in cycle[:-1]]
        skill_names = [self.udg.global_action_nodes[n].parent_skill_name for n in cycle[:-1]]
        
        return CyclicPath(
            path_action_ids=cycle,
            path_skill_ids=skill_ids,
            path_skill_names=skill_names,
            path_edges=edges,
            hop_count=len(cycle),
            total_affinity=total_aff,
            avg_semantic_sim=total_sem / len(cycle) if cycle else 0
        )
    
    def _find_bidirectional_pairs(self) -> List[Tuple[str, str]]:
        """Pre-filter: find all skill pairs with bidirectional connections.

        Iterates over all global edges and counts bidirectional connections
        between each skill pair. Only retains pairs where both A→B and B→A have edges.
        """
        from collections import defaultdict
        
        # Count edges for each skill pair
        pair_stats = defaultdict(lambda: [0, 0])  # [a_to_b_count, b_to_a_count]
        
        for (src, tgt), edge in self.udg.global_edges.items():
            skill_a = edge.source_skill_id
            skill_b = edge.target_skill_id
            
            # Skip self-loops
            if skill_a == skill_b:
                continue
            
            # Normalize the skill pair (alphabetically)
            pair_key = tuple(sorted([skill_a, skill_b]))
            if skill_a < skill_b:
                pair_stats[pair_key][0] += 1  # a_to_b
            else:
                pair_stats[pair_key][1] += 1  # b_to_a
        
        # Filter to pairs that have edges in both directions
        candidates = []
        for (skill_a, skill_b), (a2b, b2a) in pair_stats.items():
            if a2b > 0 and b2a > 0:
                candidates.append((skill_a, skill_b))
        
        return candidates
    
    def find_vulnerable_paths(self, batch_mode: bool = False, output_dir: str = None) -> List[CyclicPath]:
        """Main entry point: enumerate all simple cycles with k>=min_hop on the UDG (no bucketing, no sampling).

        Algorithm: Tarjan SCC + Johnson's simple cycle enumeration (Paper Algorithm 1).
          1. Build networkx.DiGraph over the full set of ActionNodes
          2. Use nx.strongly_connected_components to obtain all SCCs with size>=2
          3. Run nx.simple_cycles(length_bound=6) on each SCC sub-graph
          4. Filter to simple cycles with k>=min_hop
          5. Deduplicate via start-node rotation
          6. Resolve all to CyclicPath and return

        Parameters:
            batch_mode: whether to enable batch mode (process per SCC, saving memory)
            output_dir: directory for saving intermediate results in batch mode

        Bucketing / sampling / sorting logic is handled by the caller (experiment scripts).
        Falls back to the original pair-wise implementation when networkx is unavailable.
        """
        if not HAS_NETWORKX:
            print("[WARN] networkx is not installed; falling back to pair-wise implementation")
            return self._find_vulnerable_paths_pairwise_legacy()

        import gc
        import time
        import json

        print(f"\n{'='*60}")
        print("Algorithm 1: SCC + Johnson Cycle Enumeration (return-all)")
        if batch_mode:
            print("Mode: Batch (per-SCC processing, memory efficient)")
        print(f"{'='*60}")

        t0 = time.time()

        # Step 1: build networkx DiGraph
        print("\n[Step 1] Building the full graph (ActionNode-level DiGraph)...")
        G = nx.DiGraph()
        for action_id in self.udg.global_action_nodes:
            G.add_node(action_id)
        for (src, tgt), edge in self.udg.global_edges.items():
            G.add_edge(src, tgt, weight=edge.affinity_score)
        print(f"[INFO] |V|={G.number_of_nodes()}, |E|={G.number_of_edges()}")

        # Step 2: Tarjan SCC; retain components with size>=2
        print("\n[Step 2] Tarjan SCC...")
        all_sccs = list(nx.strongly_connected_components(G))
        sccs = [c for c in all_sccs if len(c) >= 2]
        print(f"[INFO] {len(all_sccs)} SCCs total; {len(sccs)} have size>=2")

        if not sccs:
            print("[WARN] No SCC with size>=2 exists; no cross-node cycles are present in the graph")
            self.cyclic_paths = []
            return []

        # Step 3: Run Johnson's simple cycle enumeration on each SCC.
        # Enumerate by hop-length buckets with no quantity limit; return all discovered cycles.
        LENGTH_BOUND = 6
        
        if batch_mode:
            return self._find_cycles_batch_mode(G, sccs, LENGTH_BOUND, t0, output_dir)
        else:
            return self._find_cycles_normal_mode(G, sccs, LENGTH_BOUND, t0)
    
    def _find_cycles_normal_mode(self, G, sccs, LENGTH_BOUND, t0) -> List[CyclicPath]:
        """Normal mode: load all cycles into memory at once."""
        print(f"\n[Step 3] Johnson simple cycle enumeration (length_bound={LENGTH_BOUND}, hop ∈ [{self.min_hop},{LENGTH_BOUND}])...")
        raw_cycles: List[List[str]] = []
        for idx, scc in enumerate(sccs):
            sub = G.subgraph(scc).copy()
            print(f"\n  [Enumerate] SCC#{idx} (node count={len(scc)})")
            per_hop_stats = {}
            for hop_target in range(self.min_hop, LENGTH_BOUND + 1):
                kept_this_hop = 0
                seen_this_hop = 0
                print(f"    [Progress] Starting enumeration for hop={hop_target}...", end="", flush=True)
                try:
                    for cyc in nx.simple_cycles(sub, length_bound=hop_target):
                        if len(cyc) != hop_target:
                            continue
                        seen_this_hop += 1
                        raw_cycles.append(cyc)
                        kept_this_hop += 1
                        if kept_this_hop % 1000 == 0:
                            print(f"\r    [Progress] hop={hop_target}, found {kept_this_hop} so far...", end="", flush=True)
                except Exception as e:
                    print(f"\r    [WARN] hop={hop_target} enumeration exception: {type(e).__name__}: {e}")
                    continue
                print(f"\r    [Done] hop={hop_target}: found {kept_this_hop}")
                per_hop_stats[hop_target] = kept_this_hop
            if any(v > 0 for v in per_hop_stats.values()):
                fragments = []
                for h, k in per_hop_stats.items():
                    if k > 0:
                        fragments.append(f"hop{h}={k}")
                print(f"  SCC#{idx} |V|={len(scc)}: " + " ".join(fragments))
        print(f"[INFO] Total raw simple cycles in the graph (k∈[{self.min_hop},{LENGTH_BOUND}]): {len(raw_cycles)}")

        if not raw_cycles:
            print("[WARN] No simple cycles found satisfying k>=min_hop")
            self.cyclic_paths = []
            return []

        # Step 4: Deduplicate by start-node rotation
        print("\n[Step 4] Deduplicating by start-node rotation...")
        dedup_cycles = self._dedup_cycles_by_rotation(raw_cycles)
        print(f"[INFO] After deduplication: {len(dedup_cycles)} unique cycles remain")

        # Step 5: Resolve into CyclicPath objects (all)
        print("\n[Step 5] Resolving into CyclicPath objects (full set)...")
        P_vuln: List[CyclicPath] = []
        skipped = 0
        for cyc in dedup_cycles:
            cyclic_path = self._resolve_action_path_global(cyc)
            if cyclic_path is None:
                skipped += 1
                continue
            P_vuln.append(cyclic_path)
        if skipped:
            print(f"  [INFO] Skipped {skipped} due to missing edges")

        self.cyclic_paths = P_vuln
        elapsed = time.time() - t0
        gc.collect()
        print(f"\n{'='*60}")
        print(f"[RESULT] Enumerated {len(P_vuln)} deduplicated cyclic paths in total (elapsed {elapsed:.2f}s)")
        print(f"{'='*60}")
        return P_vuln
    
    def _find_cycles_batch_mode(self, G, sccs, LENGTH_BOUND, t0, output_dir: str) -> List[CyclicPath]:
        """Batch mode: process per SCC, immediately save to file, and release memory"""
        import gc
        import os
        import time
        from pathlib import Path
        
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = None
        
        all_cyclic_paths: List[CyclicPath] = []
        total_cycles_count = 0
        
        print(f"\n[Step 3] Batch cycle enumeration (length_bound={LENGTH_BOUND}, hop ∈ [{self.min_hop},{LENGTH_BOUND}])...")
        
        for idx, scc in enumerate(sccs):
            print(f"\n{'='*50}")
            print(f"  [Batch {idx+1}/{len(sccs)}] Processing SCC#{idx} (node count={len(scc)})")
            print(f"{'='*50}")
            batch_start = time.time()
            
            # Copy only the subgraph of the current SCC
            sub = G.subgraph(scc).copy()
            batch_cycles: List[List[str]] = []
            
            # Enumerate all hop lengths for the current SCC
            for hop_target in range(self.min_hop, LENGTH_BOUND + 1):
                kept_this_hop = 0
                print(f"    [Progress] Starting enumeration for hop={hop_target}...", end="", flush=True)
                try:
                    for cyc in nx.simple_cycles(sub, length_bound=hop_target):
                        if len(cyc) != hop_target:
                            continue
                        batch_cycles.append(cyc)
                        kept_this_hop += 1
                        if kept_this_hop % 1000 == 0:
                            print(f"\r    [Progress] hop={hop_target}, found {kept_this_hop} so far...", end="", flush=True)
                except Exception as e:
                    print(f"\r    [WARN] hop={hop_target} enumeration exception: {type(e).__name__}: {e}")
                    continue
                print(f"\r    [Done] hop={hop_target}: found {kept_this_hop}")
                total_cycles_count += kept_this_hop
            
            print(f"  [INFO] SCC#{idx} raw cycle count: {len(batch_cycles)}")
            
            # Deduplicate the current batch
            print(f"    [Dedup] Start-node rotation dedup...", end="", flush=True)
            dedup_cycles = self._dedup_cycles_by_rotation(batch_cycles)
            print(f" after dedup: {len(dedup_cycles)}")
            
            # Immediately release raw cycle memory
            del batch_cycles
            gc.collect()
            
            # Resolve into CyclicPath
            print(f"    [Convert] Resolving into CyclicPath...", end="", flush=True)
            batch_paths: List[CyclicPath] = []
            skipped = 0
            for cyc in dedup_cycles:
                cyclic_path = self._resolve_action_path_global(cyc)
                if cyclic_path is None:
                    skipped += 1
                    continue
                batch_paths.append(cyclic_path)
            print(f" done (skipped {skipped})")
            
            # Save to file (if output_dir is specified)
            if output_path:
                batch_file = output_path / f"batch_scc{idx}.json"
                batch_data = []
                for path in batch_paths:
                    batch_data.append({
                        "cycle_nodes": path.path_action_ids,
                        "skill_sequence": path.path_skill_ids,
                        "skill_names": path.path_skill_names,
                        "hop_count": path.hop_count,
                        "total_affinity": path.total_affinity,
                        "avg_semantic_sim": path.avg_semantic_sim,
                    })
                with open(batch_file, 'w', encoding='utf-8') as f:
                    json.dump(batch_data, f, ensure_ascii=False, indent=2)
                print(f"    [Save] Saved to {batch_file}")
            
            # Accumulate results
            all_cyclic_paths.extend(batch_paths)
            
            # Release current batch memory
            del batch_paths
            del dedup_cycles
            del sub
            gc.collect()
            
            batch_elapsed = time.time() - batch_start
            print(f"  [INFO] SCC#{idx} processing complete (elapsed {batch_elapsed:.2f}s, cumulative {len(all_cyclic_paths)} paths)")
        
        # Clean up the full graph
        del G
        gc.collect()
        
        self.cyclic_paths = all_cyclic_paths
        elapsed = time.time() - t0
        print(f"\n{'='*60}")
        print(f"[RESULT] Batch mode complete")
        print(f"  - Total SCCs: {len(sccs)}")
        print(f"  - Total raw cycles: {total_cycles_count}")
        print(f"  - Cycles after dedup: {len(all_cyclic_paths)}")
        print(f"  - Total elapsed: {elapsed:.2f}s")
        if output_path:
            print(f"  - Output directory: {output_path}")
        print(f"{'='*60}")
        return all_cyclic_paths

    def _dedup_cycles_by_rotation(self, cycles: List[List[str]]) -> List[List[str]]:
        """The same simple cycle may be enumerated multiple times by simple_cycles
        from different starting nodes; deduplicate by normalizing to a form where
        the minimum element serves as the starting point.
        """
        seen: Set[Tuple[str, ...]] = set()
        unique: List[List[str]] = []
        for cyc in cycles:
            if not cyc:
                continue
            min_idx = cyc.index(min(cyc))
            normalized = tuple(cyc[min_idx:] + cyc[:min_idx])
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(cyc)
        return unique

    def _sum_cycle_affinity(self, cyc: List[str]) -> float:
        """Sum the affinity_score of all edges on the cycle; returns -inf when an edge is missing (invalid cycle)."""
        total = 0.0
        n = len(cyc)
        for i in range(n):
            src = cyc[i]
            tgt = cyc[(i + 1) % n]
            edge = self.udg.global_edges.get((src, tgt))
            if edge is None:
                return float("-inf")
            total += edge.affinity_score
        return total

    def _resolve_action_path_global(self, cyc: List[str]) -> Optional[CyclicPath]:
        """Resolve the action_id sequence returned by nx.simple_cycles into a CyclicPath.

        The cycles returned by nx.simple_cycles do not repeat the tail node
        (e.g., [A,B,C] represents A->B->C->A), so we manually close the cycle
        once to retrieve all edges.
        """
        edges: List[DirectedEdge] = []
        total_aff = 0.0
        total_sem = 0.0
        n = len(cyc)
        for i in range(n):
            src = cyc[i]
            tgt = cyc[(i + 1) % n]
            edge = self.udg.global_edges.get((src, tgt))
            if edge is None:
                return None
            edges.append(edge)
            total_aff += edge.affinity_score
            total_sem += edge.semantic_similarity

        skill_ids = [self.udg.global_action_nodes[n_].parent_skill_id for n_ in cyc]
        skill_names = [self.udg.global_action_nodes[n_].parent_skill_name for n_ in cyc]

        return CyclicPath(
            path_action_ids=list(cyc),
            path_skill_ids=skill_ids,
            path_skill_names=skill_names,
            path_edges=edges,
            hop_count=n,
            total_affinity=total_aff,
            avg_semantic_sim=total_sem / n if n else 0.0
        )

    def _find_vulnerable_paths_pairwise_legacy(self) -> List[CyclicPath]:
        """Legacy pair-wise implementation, used as a fallback only when networkx is unavailable.

        Logic: first find bidirectional skill pairs, then run DFS on the local
        subgraph of each pair to find 2-skill cycles.
        Limitation: only discovers 2-skill cycles; does not cover the N-skill
        combinatorial surface promised in the paper.
        """
        import gc

        print(f"\n{'='*60}")
        print("Algorithm 1 [LEGACY]: Pair-wise Skill Cycle Detection")
        print(f"{'='*60}")

        print("\n[Step 1] Pre-filtering skill pairs with bidirectional connections...")
        candidate_pairs = self._find_bidirectional_pairs()
        print(f"[INFO] Filtered {len(candidate_pairs)} candidate pairs from {len(self.udg.skill_subgraphs)} skills")

        if not candidate_pairs:
            print("[WARN] No bidirectional skill pairs found; cycles cannot be formed")
            return []

        print("\n[Step 2] Executing DFS on candidate pairs to find cycles...")
        P_vuln = []
        max_cycles_per_pair = 5
        pair_count = 0

        for skill_a, skill_b in candidate_pairs:
            pair_count += 1
            cycles = self._find_cycles_in_pair(skill_a, skill_b, max_cycles_per_pair=max_cycles_per_pair)
            if cycles:
                skill_a_name = self.udg.skill_subgraphs[skill_a].skill_name
                skill_b_name = self.udg.skill_subgraphs[skill_b].skill_name
                for cycle in cycles:
                    cyclic_path = self._resolve_action_path_for_pair(cycle, skill_a, skill_b)
                    if cyclic_path:
                        P_vuln.append(cyclic_path)
                        print(f"  [FOUND] ({skill_a_name} <-> {skill_b_name}) "
                              f"k={cyclic_path.hop_count}, affinity={cyclic_path.total_affinity:.2f}")
            del cycles
            if pair_count % 3 == 0:
                gc.collect()

        self.cyclic_paths = P_vuln
        print(f"\n{'='*60}")
        print(f"[RESULT] Checked {pair_count} candidate skill pairs; found {len(P_vuln)} cyclic paths")
        print(f"{'='*60}")
        return P_vuln
    
    def get_path_details(self, path: CyclicPath) -> Dict:
        node_details = []
        for action_id in path.path_action_ids:
            action = self.udg.global_action_nodes[action_id]
            node_details.append({
                'action_id': action_id,
                'skill_id': action.parent_skill_id,
                'skill_name': action.parent_skill_name,
                'command': f"{action.command_chain.tool} {action.command_chain.subcommand}",
                'description': action.description[:80],
            })
        
        edge_details = []
        for edge in path.path_edges:
            edge_details.append({
                'source_skill': self.udg.global_action_nodes[edge.source_action_id].parent_skill_name,
                'target_skill': self.udg.global_action_nodes[edge.target_action_id].parent_skill_name,
                'affinity': round(edge.affinity_score, 4),
                'param_flow': edge.parameter_flow
            })
        
        return {
            'hop_count': path.hop_count,
            'total_affinity': round(path.total_affinity, 4),
            'avg_semantic_sim': round(path.avg_semantic_sim, 4),
            'skill_sequence': path.path_skill_names,
            'nodes': node_details,
            'edges': edge_details,
            'cycle_sequence': ' -> '.join(path.path_skill_names)
        }
    
    def export_results(self, output_path: str):
        results = {
            'metadata': {
                'min_hop': self.min_hop,
                'vulnerable_paths_found': len(self.cyclic_paths)
            },
            'vulnerable_paths': [self.get_path_details(p) for p in self.cyclic_paths]
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Pathfinding results exported: {output_path}")
