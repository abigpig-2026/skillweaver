"""
Stage 1: Skill Parsing (corresponding to Paper Section 4.1)

Parses unstructured community Skill documentation into structured SkillNode representations.
Adopts a hybrid strategy: a lightweight symbolic parser (regex/AST) is used by default,
with fallback to LLM-assisted extraction when the parameter-type recognition rate
falls below threshold θ_io.

Core functionality:
- Parse SKILL.md files, extracting action nodes and input/output constraints
- Extract command chains, corresponding to the workflow-step chains H in the paper
- Encode action descriptions into TF-IDF semantic vectors (corresponding to paper formula a = <c_step, I, O, v>)
- Construct SkillNode representations (corresponding to paper formula S = (A, V, H, v_s))

Security notice: This code is intended solely for security research and red-team testing,
aiming to help developers identify and remediate potential compositional vulnerabilities
in agent systems.
"""

import os
import re
import ast
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


@dataclass
class ActionConstraint:
    """Parameter constraints in the action constraint tuple

    Corresponds to I_i (input constraints) and O_i (output constraints) in the paper.
    Derived through static AST parsing of the skill's underlying execution scripts.
    """
    name: str
    param_type: str  # 'string', 'number', 'boolean', 'json', 'file', 'url', 'unknown'
    required: bool = True
    description: str = ""
    schema: Optional[Dict] = None  # JSON Schema if available
    
    def __hash__(self):
        return hash((self.name, self.param_type, self.required))


@dataclass
class CommandChain:
    """Command chain — the C_i field in the paper

    Represents the low-level physical execution flows implicitly invoked
    by the skill. Examples: gh pr checks, agent-browser snapshot, curl -s
    """
    tool: str           # Top-level tool (gh, agent-browser, curl)
    subcommand: str     # Subcommand (pr, snapshot, open)
    action: str         # Concrete action (checks, -i, <url>)
    flags: List[str] = field(default_factory=list)
    output_format: str = "text"
    description: str = ""


@dataclass
class ActionNode:
    """Action node — corresponding to paper formula (1): a = ⟨cmd, I, O, v⟩

    Each action node is a node in the UDG graph, containing:
    - cmd: command chain (tool + subcommand + action)
    - I: set of input constraints
    - O: set of output constraints
    - v: TF-IDF semantic vector of the action description text
    """
    action_id: str
    command_chain: CommandChain
    inputs: List[ActionConstraint] = field(default_factory=list)
    outputs: List[ActionConstraint] = field(default_factory=list)
    tfidf_vector: Optional[np.ndarray] = None
    description: str = ""


@dataclass
class SkillNode:
    """Skill node — corresponding to paper formula: S = (A, V, H, v_s)

    Each skill s_i is mapped as a collection containing multiple action nodes,
    where:
    - id: unique skill identifier (corresponding to paper's skill_id)
    - name: name of the skill
    - A (actions): set of action nodes for this skill (each with its own TF-IDF vector)
    - V (action_verbs): list of action verbs (corresponding to paper's V)
    - H (command_chains): workflow-step / command chains (corresponding to paper's H)
    - v_s (skill_vector): skill-level semantic vector (optional, used for holistic similarity computation)
    """
    skill_id: str
    name: str
    description: str
    source_file: str

    # Fields corresponding to paper formula S = (A, V, H, v_s)
    actions: List[ActionNode] = field(default_factory=list)  # A - set of action nodes
    action_verbs: List[str] = field(default_factory=list)    # V - list of action verbs
    command_chains: List[CommandChain] = field(default_factory=list)  # H - workflow-step / command chains
    skill_vector: Optional[np.ndarray] = None  # v_s - skill-level semantic vector (optional)

    # Original content (retained for debugging and export)
    raw_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Fields for backward compatibility with legacy code (marked as deprecated)
    inputs: List[ActionConstraint] = field(default_factory=list)   # Deprecated: use actions[i].inputs
    outputs: List[ActionConstraint] = field(default_factory=list)  # Deprecated: use actions[i].outputs
    semantic_vector: Optional[np.ndarray] = None  # Deprecated: use skill_vector or actions[i].tfidf_vector
    
    def get_vector_dim(self) -> int:
        if self.skill_vector is not None:
            return len(self.skill_vector)
        if self.actions and self.actions[0].tfidf_vector is not None:
            return len(self.actions[0].tfidf_vector)
        return 0


class TFIDFEncoder:
    """TF-IDF semantic encoder — required by Paper Section 4.1

    Maps action description text into the TF-IDF vector space.
    Corresponds to the v field in paper formula (1).

    Usage:
    1. Collect all action description texts
    2. Call fit() to build the vocabulary
    3. Call encode() to convert text into TF-IDF vectors
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            min_df=1,
            max_df=0.95,
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents='unicode',
            lowercase=True
        )
        self.is_fitted = False
        self.corpus = []
    
    def fit(self, texts: List[str]):
        """Build the TF-IDF vocabulary

        Args:
            texts: list of all action description texts
        """
        self.corpus = texts
        self.vectorizer.fit(texts)
        self.is_fitted = True
        print(f"[INFO] TF-IDF Encoder: vocabulary built, vocabulary size={len(self.vectorizer.vocabulary_)}")
    
    def encode(self, text: str) -> np.ndarray:
        """Encode text into a TF-IDF vector

        Args:
            text: action description text

        Returns:
            TF-IDF vector (numpy array)
        """
        if not self.is_fitted:
            raise ValueError("TF-IDF encoder not fitted; call fit() first")
        
        vector = self.vectorizer.transform([text]).toarray()[0]
        return vector
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode texts in batch

        Args:
            texts: list of texts

        Returns:
            TF-IDF vector matrix (n_samples, n_features)
        """
        if not self.is_fitted:
            raise ValueError("TF-IDF encoder not fitted; call fit() first")
        
        matrix = self.vectorizer.transform(texts).toarray()
        return matrix


class SkillGraphBuilder:
    """Neuro-symbolic skill graph builder

    Implements the dual-plane neuro-symbolic feature extraction engine
    described in Paper Section 4.1:
    1. Symbolic plane: extracts action nodes and input/output constraints
       via static AST parsing.
    2. Neural plane: obtains action-level vector representations
       via the TF-IDF encoder.

    Converts heterogeneous, unstructured skills into standardized
    state-transition nodes.
    """

    def __init__(self,
                 use_llm_io_extraction: bool = False,
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat"):
        """Initialize the skill graph builder.

        Args:
            use_llm_io_extraction: whether to use LLM for IO constraint extraction (for non-standard SKILL.md files)
            api_key: DeepSeek API key (reads from environment variable if not provided)
            model: model name to use
        """
        self.tfidf_encoder = TFIDFEncoder()
        self.nodes: Dict[str, SkillNode] = {}
        self._action_descriptions_cache: List[str] = []  # caches all action descriptions for TF-IDF fitting

        # LLM IO extraction configuration
        self.use_llm_io_extraction = use_llm_io_extraction
        self.model = model
        
        if use_llm_io_extraction:
            if not HAS_OPENAI:
                raise ImportError("The openai library is required: pip install openai")
            
            self.llm_api_key = api_key or DEEPSEEK_API_KEY
            if not self.llm_api_key:
                raise ValueError("Set the DEEPSEEK_API_KEY environment variable or pass the api_key parameter during initialization")
            
            self.llm_client = OpenAI(
                api_key=self.llm_api_key,
                base_url="https://api.deepseek.com/v1"
            )
            print("[INFO] LLM-assisted IO extraction enabled (using DeepSeek)")
        else:
            self.llm_client = None

        # Action verb dictionary (for symbolic analysis)
        self.action_keywords = {
            'read', 'write', 'get', 'fetch', 'retrieve', 'create', 'update', 'delete',
            'search', 'find', 'query', 'parse', 'convert', 'transform', 'generate',
            'analyze', 'process', 'send', 'receive', 'download', 'upload', 'list',
            'show', 'display', 'render', 'extract', 'filter', 'sort', 'merge',
            'split', 'compress', 'decompress', 'encode', 'decode', 'format',
            'validate', 'verify', 'check', 'scan', 'monitor', 'notify', 'report',
            'summarize', 'translate', 'synthesize', 'execute', 'run', 'call',
            'invoke', 'trigger', 'schedule', 'cancel', 'retry', 'loop', 'iterate'
        }
        
        # Data entity dictionary
        self.data_keywords = {
            'file', 'json', 'xml', 'csv', 'text', 'string', 'number', 'boolean',
            'image', 'video', 'audio', 'url', 'uri', 'path', 'api', 'request',
            'response', 'input', 'output', 'result', 'data', 'content', 'document',
            'message', 'email', 'notification', 'log', 'record', 'entry', 'item',
            'list', 'array', 'object', 'map', 'dictionary', 'set', 'stream',
            'buffer', 'cache', 'database', 'table', 'schema', 'template'
        }
    
    def _finalize_tfidf_vectors(self):
        """After all skills are parsed, build the TF-IDF vocabulary and generate vectors.

        Must be called after parse_skill_directory().
        """
        if not self._action_descriptions_cache:
            print("[WARN] No action description texts available; skipping TF-IDF encoding")
            return
        
        print(f"\n[INFO] Building TF-IDF vectors ({len(self._action_descriptions_cache)} actions total)...")
        self.tfidf_encoder.fit(self._action_descriptions_cache)
        
        # Generate TF-IDF vectors for each action node
        total_actions = 0
        for skill_id, node in self.nodes.items():
            for action in node.actions:
                action.tfidf_vector = self.tfidf_encoder.encode(action.description)
                total_actions += 1
        
        print(f"[INFO] TF-IDF vector generation complete: {total_actions} action nodes, vector dimension={self.tfidf_encoder.vectorizer.transform(['']).shape[1]}")
    
    def _generate_skill_vector(self, content: str, metadata: Dict, action_verbs: List[str]) -> Optional[np.ndarray]:
        """Generate a skill-level semantic vector (optional).

        Encodes the entire Skill document using TF-IDF.
        """
        skill_text = f"{metadata.get('description', '')}. "
        skill_text += f"Actions: {', '.join(action_verbs)}. "
        skill_text += content[:500]
        
        # Cache and encode later
        self._action_descriptions_cache.append(skill_text)
        return None  # Skill-level vector is optional; deferred
    
    def _extract_io_for_command(self, command: CommandChain, content: str) -> Tuple[List[ActionConstraint], List[ActionConstraint]]:
        """Extract IO constraints for a specific command chain.

        Extracts relevant input and output parameters based on the command chain's
        context (tool, subcommand, flags).
        """
        inputs = []
        outputs = []
        
        # Extract parameter clues from the command chain
        cmd_context = f"{command.tool} {command.subcommand} {command.action}"
        cmd_flags = ' '.join(command.flags)
        cmd_full = f"{cmd_context} {cmd_flags}"
        
        # Find parameters related to the command
        cmd_lower = cmd_full.lower()
        
        # Infer input type from command keywords
        if any(kw in cmd_lower for kw in ['read', 'get', 'fetch', 'search', 'query']):
            inputs.append(ActionConstraint(
                name="query_input",
                param_type="string",
                required=True,
                description=f"Input for {command.tool} {command.subcommand}"
            ))
        
        if any(kw in cmd_lower for kw in ['file', 'path', 'input']):
            inputs.append(ActionConstraint(
                name="file_path",
                param_type="file",
                required=False,
                description="File path parameter"
            ))
        
        if any(kw in cmd_lower for kw in ['url', 'http', 'endpoint']):
            inputs.append(ActionConstraint(
                name="url",
                param_type="url",
                required=False,
                description="URL parameter"
            ))
        
        # Infer output type from command keywords
        if any(kw in cmd_lower for kw in ['write', 'create', 'generate', 'output']):
            outputs.append(ActionConstraint(
                name="generated_output",
                param_type="string",
                required=True,
                description=f"Output from {command.tool} {command.subcommand}"
            ))
        
        if '--json' in cmd_lower or '-json' in cmd_lower:
            outputs.append(ActionConstraint(
                name="json_result",
                param_type="json",
                required=True,
                description="JSON formatted output"
            ))
        
        # If nothing was extracted, use defaults
        if not inputs:
            inputs.append(ActionConstraint(
                name="context",
                param_type="unknown",
                required=True,
                description="Fallback input: IO constraint not extractable"
            ))
        
        if not outputs:
            outputs.append(ActionConstraint(
                name="result",
                param_type="unknown",
                required=True,
                description="Fallback output: IO constraint not extractable"
            ))
        
        return inputs, outputs
    
    def _generate_action_description(self, command: CommandChain, action_verbs: List[str], content: str) -> str:
        """Generate action description text (for TF-IDF vectorization).

        Generates descriptive text based on the command chain and context.
        """
        parts = []
        
        # Command description
        if command.description:
            parts.append(command.description)
        else:
            parts.append(f"{command.tool} {command.subcommand} {command.action}")
        
        # Append related action verbs
        related_verbs = []
        cmd_lower = f"{command.tool} {command.subcommand}".lower()
        for verb in action_verbs:
            if verb in cmd_lower or any(kw in cmd_lower for kw in ['get', 'fetch', 'read'] if verb in ['get', 'fetch', 'read', 'retrieve']):
                related_verbs.append(verb)
        
        if related_verbs:
            parts.append(' '.join(related_verbs))
        
        # Append command flags
        if command.flags:
            parts.append(' '.join(command.flags[:3]))
        
        return ' '.join(parts)
    
    def _call_llm_for_io_extraction(self, skill_content: str) -> Tuple[List[ActionConstraint], List[ActionConstraint]]:
        """Use LLM to extract IO constraints for a skill.

        Args:
            skill_content: full content of the SKILL.md file

        Returns:
            (inputs, outputs) tuple
        """
        system_prompt = """你是一个专业的技能分析专家。你的任务是从 SKILL.md 文件中精确提取输入输出约束。

请分析给定的技能文件内容，提取：
1. **输入约束 (Inputs)**: 技能需要接收哪些类型的数据或参数
2. **输出约束 (Outputs)**: 技能会产生哪些类型的数据或结果

对于每个输入和输出，请提供：
- name: 参数名称（简洁明确的英文标识符）
- param_type: 参数类型（从以下选择：string, number, boolean, json, file, image, video, audio, url, list, object, unknown）
- required: 是否必需（true 或 false）
- description: 简短描述（英文，20-50词）

请以 JSON 格式返回，格式如下：
```json
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
```

重要规则：
- 只提取技能真正需要/产生的数据，不要臆想
- 如果技能确实没有明确定义 IO，返回空数组 []
- 参数类型必须从指定列表中选择
- 返回必须是有效的 JSON，不要添加额外解释"""

        prompt = f"""请分析以下 SKILL.md 文件内容，提取输入输出约束：

{skill_content[:3000]}

请按照要求的 JSON 格式返回结果。"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON (may be embedded in a code block)
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find the first { and the last }
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx:end_idx+1]
                else:
                    json_str = content
            
            # Clean the JSON string
            json_str = json_str.strip()
            
            # Return empty if the string is empty
            if not json_str:
                print(f"[WARN] LLM returned empty content")
                return [], []

            # Try to parse JSON; attempt repair if it fails
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as je:
                print(f"[WARN] JSON parse failed: {je}")
                print(f"[DEBUG] LLM returned content length: {len(content)} characters")

                # Attempt to repair JSON: truncate to the last complete object
                # Find content before the last "}", attempt to complete it
                try:
                    # Method 1: try to extract complete inputs or outputs arrays
                    fixed_result = {"inputs": [], "outputs": []}
                    
                    # Extract inputs
                    inputs_match = re.search(r'"inputs"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                    if inputs_match:
                        inputs_str = inputs_match.group(1)
                        # Attempt repair: find the last complete object
                        last_complete = inputs_str.rfind('}')
                        if last_complete != -1:
                            inputs_str = inputs_str[:last_complete+1]
                            # Remove possible trailing comma
                            inputs_str = inputs_str.rstrip().rstrip(',')
                            fixed_result['inputs'] = json.loads(f'[{inputs_str}]')
                    
                    # Extract outputs
                    outputs_match = re.search(r'"outputs"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                    if outputs_match:
                        outputs_str = outputs_match.group(1)
                        last_complete = outputs_str.rfind('}')
                        if last_complete != -1:
                            outputs_str = outputs_str[:last_complete+1]
                            outputs_str = outputs_str.rstrip().rstrip(',')
                            fixed_result['outputs'] = json.loads(f'[{outputs_str}]')
                    
                    if fixed_result['inputs'] or fixed_result['outputs']:
                        print(f"[INFO] JSON repair succeeded: {len(fixed_result['inputs'])} inputs, {len(fixed_result['outputs'])} outputs")
                        result = fixed_result
                    else:
                        print(f"[WARN] JSON repair failed, returning empty result")
                        return [], []
                        
                except Exception as fix_error:
                    print(f"[WARN] JSON repair also failed: {fix_error}")
                    return [], []
            
            # Parse into ActionConstraint objects
            inputs = []
            for inp in result.get("inputs", []):
                inputs.append(ActionConstraint(
                    name=inp.get("name", "unknown"),
                    param_type=inp.get("param_type", "unknown"),
                    required=inp.get("required", True),
                    description=inp.get("description", "LLM extracted input")
                ))
            
            outputs = []
            for out in result.get("outputs", []):
                outputs.append(ActionConstraint(
                    name=out.get("name", "result"),
                    param_type=out.get("param_type", "unknown"),
                    required=out.get("required", True),
                    description=out.get("description", "LLM extracted output")
                ))
            
            return inputs, outputs
            
        except Exception as e:
            import traceback
            print(f"[WARN] LLM IO extraction failed: {e}")
            print(f"[DEBUG] Exception traceback: {traceback.format_exc()}")
            return [], []

    def parse_skill_file(self, skill_path: str) -> Optional[SkillNode]:
        """Parse a single Skill file, extracting action constraint tuples.

        Follows paper formula (3): s = ⟨id, name, A, V_act, C_cmd, v_sem⟩
        """
        path = Path(skill_path)

        if not path.exists():
            print(f"[ERROR] Skill file does not exist: {skill_path}")
            return None

        # Read SKILL.md
        skill_md_path = path / "SKILL.md" if path.is_dir() else path
        if not skill_md_path.exists():
            md_files = list(path.glob("*.md")) if path.is_dir() else []
            if md_files:
                skill_md_path = md_files[0]
            else:
                print(f"[ERROR] SKILL.md not found: {skill_path}")
                return None

        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            return None

        # Parse metadata
        metadata = self._extract_metadata(content)

        # Extract command chains (C_cmd) — parse script files via AST
        command_chains = self._extract_command_chains(content, skill_dir=path if path.is_dir() else None)

        # Extract action keywords
        action_verbs = self._extract_action_verbs(content)

        # Create an independent action node for each command chain (paper formula (1))
        actions = []
        for idx, chain in enumerate(command_chains):
            action_id = f"action_{idx}"
            
            # Extract IO constraints for this action (based on command chain context)
            action_inputs, action_outputs = self._extract_io_for_command(chain, content)

            # Generate action description text (for TF-IDF vectorization)
            action_description = self._generate_action_description(chain, action_verbs, content)

            # Cache the description text; TF-IDF will be built later in batch
            self._action_descriptions_cache.append(action_description)
            
            action_node = ActionNode(
                action_id=action_id,
                command_chain=chain,
                inputs=action_inputs,
                outputs=action_outputs,
                tfidf_vector=None,  # generated later in _finalize_tfidf_vectors()
                description=action_description
            )
            actions.append(action_node)

        # If no command chain was extracted, create a default action node
        if not actions:
            default_chain = CommandChain(
                tool="unknown",
                subcommand="",
                action="",
                description=metadata.get('description', '')
            )
            action_description = metadata.get('description', 'Unknown action')
            self._action_descriptions_cache.append(action_description)
            
            # Extract skill-level IO constraints (as IO for the default action)
            inputs, outputs = self._extract_io_constraints(content)
            
            actions.append(ActionNode(
                action_id="action_0",
                command_chain=default_chain,
                inputs=inputs,
                outputs=outputs,
                tfidf_vector=None,
                description=action_description
            ))

        # Generate skill-level semantic vector (optional, for holistic similarity)
        skill_vector = self._generate_skill_vector(content, metadata, action_verbs)

        # Build the node ID
        skill_name = metadata.get('name', path.name)
        skill_id = f"skill_{skill_name}_{hashlib.md5(str(path).encode()).hexdigest()[:8]}"

        # Backward compatibility: retain inputs/outputs/semantic_vector fields
        # Derive IO from the first action node (if available)
        compat_inputs = actions[0].inputs if actions else []
        compat_outputs = actions[0].outputs if actions else []
        compat_semantic_vector = actions[0].tfidf_vector if actions else None

        node = SkillNode(
            skill_id=skill_id,
            name=skill_name,
            description=metadata.get('description', ''),
            source_file=str(skill_md_path),
            actions=actions,  # paper formula (3): A field
            action_verbs=action_verbs,  # V_act field
            command_chains=command_chains,  # C_cmd field
            skill_vector=skill_vector,  # v_sem field
            raw_content=content[:2000],
            metadata=metadata,
            # Backward compatibility
            inputs=compat_inputs,
            outputs=compat_outputs,
            semantic_vector=compat_semantic_vector
        )

        self.nodes[skill_id] = node
        print(f"[INFO] Parsed skill node: {skill_name} (ID: {skill_id})")
        print(f"       Action nodes: {len(actions)}, command chains: {len(command_chains)}, action verbs: {len(action_verbs)}")

        return node

    def parse_skill_directory(self, directory: str, max_skills: Optional[int] = None) -> List[SkillNode]:
        """Parse all Skills in a directory.

        Args:
            directory: path to the skill directory
            max_skills: maximum number of skills to parse (None means all)

        Returns:
            list of parsed SkillNode objects
        """
        dir_path = Path(directory)
        nodes = []
        count = 0

        if not dir_path.exists():
            print(f"[ERROR] Directory does not exist: {directory}")
            return nodes

        # Find all directories containing SKILL.md
        for skill_dir in sorted(dir_path.iterdir()):  # sorted to ensure consistent ordering
            if max_skills and count >= max_skills:
                break
            
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    node = self.parse_skill_file(str(skill_dir))
                    if node:
                        nodes.append(node)
                        count += 1

        # After all skills are parsed, build TF-IDF vectors
        self._finalize_tfidf_vectors()

        print(f"\n[INFO] Parsed {len(nodes)} skill nodes in total")
        return nodes

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter metadata."""
        metadata = {}

        yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
            for key in ['name', 'description', 'version', 'author', 'license']:
                pattern = rf'{key}:\s*(.+?)(?:\n|$)'
                match = re.search(pattern, yaml_content, re.IGNORECASE)
                if match:
                    metadata[key] = match.group(1).strip()

        if 'description' not in metadata:
            para_match = re.search(r'\n\n([^#\n].{50,500})\n', content)
            if para_match:
                metadata['description'] = para_match.group(1).strip()

        return metadata

    def _extract_io_constraints(self, content: str) -> Tuple[List[ActionConstraint], List[ActionConstraint]]:
        """Extract input/output constraints (symbolic-plane analysis)."""
        inputs = []
        outputs = []

        input_patterns = [
            r'`([^`]+)`\s*\(input\)',
            r'[Ii]nput:\s*`?([^`\n]+)`?',
            r'(?:argument|parameter|input)\s*[:：]\s*`?([^`\n]+)`?',
            r'(?:takes|accepts|requires)\s+`?([^`\n]+?)`?\s*(?:as|for)',
            r'--([a-zA-Z-]+)\s+(?:<[^>]+>|"[^"]*"|\S+)',
            r'\$([A-Z_]+)',
        ]

        output_patterns = [
            r'`([^`]+)`\s*\(output\)',
            r'[Oo]utput:\s*`?([^`\n]+)`?',
            r'(?:returns|outputs?|produces?)\s*[:：]\s*`?([^`\n]+)`?',
            r'(?:returns|outputs?|generates?|produces?)\s+(?:a|an|the)?\s*`?([^`\n]{5,100})`?',
        ]

        type_hints = {
            'url': 'url', 'uri': 'url', 'http': 'url', 'endpoint': 'url',
            'file': 'file', 'path': 'file', 'directory': 'file', 'folder': 'file',
            'json': 'json', 'xml': 'json', 'csv': 'json', 'yaml': 'json',
            'text': 'string', 'string': 'string', 'str': 'string',
            'number': 'number', 'int': 'number', 'integer': 'number', 'float': 'number',
            'bool': 'boolean', 'boolean': 'boolean', 'flag': 'boolean',
        }

        seen_inputs = set()
        for pattern in input_patterns:
            for match in re.finditer(pattern, content):
                param_name = match.group(1).strip()
                if param_name in seen_inputs or len(param_name) > 50:
                    continue
                seen_inputs.add(param_name)

                param_type = 'unknown'
                param_lower = param_name.lower()
                for hint, ptype in type_hints.items():
                    if hint in param_lower:
                        param_type = ptype
                        break

                inputs.append(ActionConstraint(
                    name=param_name,
                    param_type=param_type,
                    required=True,
                    description=f"Extracted input parameter: {param_name}"
                ))

        seen_outputs = set()
        for pattern in output_patterns:
            for match in re.finditer(pattern, content):
                output_name = match.group(1).strip()
                if output_name in seen_outputs or len(output_name) > 50:
                    continue
                seen_outputs.add(output_name)

                output_type = 'unknown'
                out_lower = output_name.lower()
                for hint, ptype in type_hints.items():
                    if hint in out_lower:
                        output_type = ptype
                        break

                outputs.append(ActionConstraint(
                    name=output_name,
                    param_type=output_type,
                    required=True,
                    description=f"Extracted output: {output_name}"
                ))

        if not inputs:
            # When nothing is extractable, fall back to "unknown" instead of "string":
            # downstream pairwise matching does not treat unknown<->* as compatible,
            # preventing all skills from appearing universally connectable
            inputs.append(ActionConstraint(
                name="context",
                param_type="unknown",
                required=True,
                description="Fallback input: IO constraint not extractable from SKILL.md"
            ))
        if not outputs:
            outputs.append(ActionConstraint(
                name="result",
                param_type="unknown",
                required=True,
                description="Fallback output: IO constraint not extractable from SKILL.md"
            ))

        # If LLM extraction is enabled and the traditional method produced
        # poor quality results (only default "unknown" fallbacks),
        # attempt to re-extract using LLM
        if self.use_llm_io_extraction and self.llm_client:
            # Determine whether LLM assistance is needed:
            # 1. Traditional method completely failed (only default "unknown" fallbacks)
            # 2. Or the traditional method produced low-quality IO (mostly "unknown" types)
            is_traditional_weak = (
                len(inputs) == 1 and inputs[0].name == "context" and inputs[0].param_type == "unknown" and
                len(outputs) == 1 and outputs[0].name == "result" and outputs[0].param_type == "unknown"
            )
            
            # Check IO quality: if most IO entries are "unknown" type, the extraction quality is poor
            unknown_input_count = sum(1 for inp in inputs if inp.param_type == 'unknown')
            unknown_output_count = sum(1 for out in outputs if out.param_type == 'unknown')
            is_io_quality_poor = (
                len(inputs) > 0 and unknown_input_count / len(inputs) > 0.5 or
                len(outputs) > 0 and unknown_output_count / len(outputs) > 0.5
            )
            
            if is_traditional_weak or is_io_quality_poor:
                if is_io_quality_poor:
                    print(f"[INFO] Traditional method produced poor IO quality ({unknown_input_count}/{len(inputs)} inputs, {unknown_output_count}/{len(outputs)} outputs are unknown); attempting LLM re-extraction...")
                else:
                    print(f"[INFO] Traditional method yielded suboptimal results; attempting LLM re-extraction of IO constraints...")
                llm_inputs, llm_outputs = self._call_llm_for_io_extraction(content)
                
                # If the LLM extracted valid IO, use the LLM results
                if llm_inputs or llm_outputs:
                    inputs = llm_inputs if llm_inputs else inputs
                    outputs = llm_outputs if llm_outputs else outputs
                    print(f"[INFO] LLM extraction succeeded: {len(inputs)} inputs, {len(outputs)} outputs")
                else:
                    print(f"[WARN] LLM extraction failed; using traditional method results")

        return inputs, outputs

    def _extract_action_verbs(self, content: str) -> List[str]:
        """Extract action verbs."""
        verbs = []
        content_lower = content.lower()

        code_blocks = re.findall(r'```\w*\n(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            commands = re.findall(r'^(?:\$\s*)?([a-zA-Z][a-zA-Z0-9_-]+)', block, re.MULTILINE)
            verbs.extend(commands)

        for keyword in self.action_keywords:
            if keyword in content_lower:
                verbs.append(keyword)

        return list(set(verbs))

    def _extract_data_entities(self, content: str) -> List[str]:
        """Extract data entities."""
        entities = []
        content_lower = content.lower()

        for keyword in self.data_keywords:
            if keyword in content_lower:
                entities.append(keyword)

        urls = re.findall(r'https?://[^\s\)]+', content)
        for url in urls:
            domain_match = re.search(r'https?://([^/]+)', url)
            if domain_match:
                entities.append(domain_match.group(1))

        return list(set(entities))

    def _extract_command_chains(self, content: str, skill_dir: Optional[Path] = None) -> List[CommandChain]:
        """Extract command chains C_i — AST-based low-level physical execution flow analysis (required by Paper Section 4.1).

        Implements the deep Abstract Syntax Tree (AST) parsing of underlying
        execution scripts (e.g., Python or Bash) as required by the paper.

        Pipeline:
        1. Scan the skill directory for all .py/.sh/.js script files
        2. Use the `ast` module for AST parsing of Python scripts
        3. Use structural parsing for Bash scripts
        4. Use regex extraction for JavaScript scripts
        5. Extract commands from markdown code blocks in SKILL.md (fallback)
        """
        chains = []
        
        if skill_dir is not None and skill_dir.exists():
            python_files = list(skill_dir.rglob("*.py"))
            bash_files = list(skill_dir.rglob("*.sh"))
            js_files = list(skill_dir.rglob("*.js")) + list(skill_dir.rglob("*.mjs"))
            
            for py_file in python_files:
                chains.extend(self._parse_python_ast(py_file))
            
            for sh_file in bash_files:
                chains.extend(self._parse_bash_script(sh_file))
            
            for js_file in js_files:
                chains.extend(self._parse_javascript(js_file))
        
        if not chains:
            chains.extend(self._extract_from_markdown(content))
        
        return chains
    
    def _parse_python_ast(self, filepath: Path) -> List[CommandChain]:
        """Perform static AST analysis on a Python script using the `ast` module.

        Extracts the following AST nodes:
        - FunctionDef/AsyncFunctionDef: function definitions
        - Call: function calls (subprocess.run, requests.get, os.system, etc.)
        - Import/ImportFrom: imported modules
        - Assign: assignment statements (containing command strings)
        """
        chains = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception:
            return chains
        
        try:
            tree = ast.parse(source_code, filename=str(filepath))
        except SyntaxError:
            return chains
        
        subprocess_tools = {'subprocess', 'os', 'sys', 'shutil', 'requests', 'urllib'}
        command_execution_funcs = {
            ('subprocess', 'run'), ('subprocess', 'call'), ('subprocess', 'Popen'),
            ('subprocess', 'check_output'), ('subprocess', 'check_call'),
            ('os', 'system'), ('os', 'popen'), ('os', 'exec'),
            ('shutil', 'copy'), ('shutil', 'move'), ('shutil', 'rmtree'),
            ('requests', 'get'), ('requests', 'post'), ('requests', 'put'),
            ('requests', 'delete'), ('requests', 'patch'),
            ('urllib', 'request'), ('urllib', 'urlopen'),
        }
        
        imported_modules = {}
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules[alias.name] = alias.asname or alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        imported_modules[f"{node.module}.{alias.name}"] = alias.asname or alias.name
            
            elif isinstance(node, ast.Call):
                chain = self._extract_python_call(node, source_code, imported_modules, command_execution_funcs)
                if chain:
                    chains.append(chain)
        
        return chains
    
    def _extract_python_call(self, node: ast.Call, source: str, imports: Dict, exec_funcs: Set) -> Optional[CommandChain]:
        """Extract a CommandChain from a Python AST Call node."""
        func_name = None
        
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func.value, ast.Attribute):
                if isinstance(node.func.value.value, ast.Name):
                    func_name = f"{node.func.value.value.id}.{node.func.value.attr}.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
        
        if not func_name:
            return None
        
        is_exec_call = False
        for module, func in exec_funcs:
            if func_name.startswith(module) and func in func_name:
                is_exec_call = True
                break
        
        if not is_exec_call:
            if any(mod in func_name for mod in {'subprocess', 'os.system', 'requests'}):
                is_exec_call = True
        
        if not is_exec_call:
            return None
        
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                args.append(arg.value)
            elif isinstance(arg, ast.List):
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        args.append(elt.value)
        
        for keyword in node.keywords:
            if keyword.arg in {'args', 'command', 'cmd', 'url', 'data'}:
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    args.append(keyword.value.value)
                elif isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            args.append(elt.value)
        
        if not args:
            return None
        
        cmd_line = ' '.join(str(a) for a in args[:5])
        parts = cmd_line.split()
        
        return CommandChain(
            tool=parts[0] if parts else func_name,
            subcommand=parts[1] if len(parts) > 1 else "",
            action=parts[2] if len(parts) > 2 else "",
            flags=[p for p in parts if p.startswith('-') or p.startswith('--')],
            output_format='text',
            description=f"[AST] {func_name}: {cmd_line[:80]}"
        )
    
    def _parse_bash_script(self, filepath: Path) -> List[CommandChain]:
        """Parse a Bash script and extract command chains."""
        chains = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return chains
        
        known_tools = {'gh', 'agent-browser', 'curl', 'npx', 'npm', 'git', 'python', 'node', 
                      'wget', 'docker', 'kubectl', 'aws', 'gcloud', 'az', 'ssh', 'scp', 'rsync'}
        output_format_patterns = {
            '--json': 'json', '-json': 'json', '--format json': 'json',
            '--output-format json': 'json', '--jq': 'json',
            '-o': 'file', '--output': 'file',
            '.png': 'image', '.jpg': 'image', '.pdf': 'pdf',
            '--yaml': 'yaml', '--csv': 'csv', '--xml': 'xml',
            '--text': 'text', '--html': 'html',
        }
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('!'):
                continue
            line = re.sub(r'^\$\s*', '', line)
            
            parts = line.split()
            if not parts:
                continue
            
            tool = parts[0]
            if tool in known_tools or any(tool.endswith(f"/{t}") for t in known_tools):
                subcommand = parts[1] if len(parts) > 1 else ""
                action = parts[2] if len(parts) > 2 else ""
                flags = [p for p in parts if p.startswith('-') or p.startswith('--')]
                
                output_format = 'text'
                line_lower = line.lower()
                for flag, fmt in output_format_patterns.items():
                    if flag in flags or flag in line_lower:
                        output_format = fmt
                        break
                
                chains.append(CommandChain(
                    tool=tool,
                    subcommand=subcommand,
                    action=action,
                    flags=flags,
                    output_format=output_format,
                    description=f"[Bash] {line[:80]}"
                ))
        
        return chains
    
    def _parse_javascript(self, filepath: Path) -> List[CommandChain]:
        """Parse a JavaScript script and extract command chains."""
        chains = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return chains
        
        # 1. child_process calls
        child_process_patterns = [
            r'(?:child_process|spawn|exec|execFile|run)\s*\(\s*["\']([^"\']+)["\']',
            r'(?:execSync|execa|shelljs)\s*\(\s*["\']([^"\']+)["\']',
            r'process\.spawn\s*\(\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in child_process_patterns:
            for match in re.finditer(pattern, content):
                cmd = match.group(1)
                parts = cmd.split()
                chains.append(CommandChain(
                    tool=parts[0] if parts else "node",
                    subcommand=parts[1] if len(parts) > 1 else "",
                    action=parts[2] if len(parts) > 2 else "",
                    flags=[p for p in parts if p.startswith('-') or p.startswith('--')],
                    output_format='text',
                    description=f"[JS] {cmd[:80]}"
                ))
        
        # 2. require imports
        require_pattern = r'(?:const|let|var)\s+\w+\s*=\s*require\s*\(\s*["\']([^"\']+)["\']\s*\)'
        for match in re.finditer(require_pattern, content):
            module_name = match.group(1)
            if any(t in module_name for t in {'child_process', 'execa', 'shelljs', 'cross-spawn'}):
                chains.append(CommandChain(
                    tool="node",
                    subcommand="require",
                    action=module_name,
                    flags=[],
                    output_format='text',
                    description=f"[JS Import] {module_name}"
                ))
        
        # 3. Extract CLI command structure (parse commands from case/switch or CLI entry points)
        filename = filepath.stem

        # Extract CLI subcommands from switch/case statements
        case_pattern = r"case\s+['\"](\w+)['\"]:"
        case_commands = re.findall(case_pattern, content)
        
        if case_commands:
            for cmd in case_commands:
                if cmd not in {'default'}:
                    chains.append(CommandChain(
                        tool="node",
                        subcommand=f"{filename}.js",
                        action=cmd,
                        flags=[],
                        output_format='text',
                        description=f"[JS CLI] node {filename}.js {cmd}"
                    ))
        
        # Extract commands from process.argv or usage strings in console.log
        usage_pattern = r"(?:node\s+)?(\w+\.js)\s+(add|remove|list|check|get|create|delete|update|search|fetch|parse|run|start|stop)\b"
        for match in re.finditer(usage_pattern, content, re.IGNORECASE):
            script_name = match.group(1)
            subcommand = match.group(2).lower()
            cmd_key = f"node {script_name} {subcommand}"
            if not any(c.action == subcommand and c.subcommand == script_name for c in chains):
                chains.append(CommandChain(
                    tool="node",
                    subcommand=script_name,
                    action=subcommand,
                    flags=[],
                    output_format='text',
                    description=f"[JS Usage] {cmd_key}"
                ))
        
        return chains
    
    def _extract_from_markdown(self, content: str) -> List[CommandChain]:
        """Extract command chains from markdown code blocks in SKILL.md (fallback)."""
        chains = []
        known_tools = {'gh', 'agent-browser', 'curl', 'npx', 'npm', 'git', 'python', 'node'}
        output_format_patterns = {
            '--json': 'json', '-json': 'json', '--format json': 'json',
            '--output-format json': 'json', '--jq': 'json',
            '-o': 'file', '--output': 'file',
            '.png': 'image', '.jpg': 'image', '.pdf': 'pdf',
            '--yaml': 'yaml', '--csv': 'csv', '--xml': 'xml',
            '--text': 'text', '--html': 'html',
        }
        
        bash_blocks = re.findall(r'```bash\n(.*?)```', content, re.DOTALL)
        for block in bash_blocks:
            for line in block.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                line = re.sub(r'^\$\s*', '', line)
                parts = line.split()
                if len(parts) < 1:
                    continue
                tool = parts[0]
                if tool not in known_tools:
                    continue
                
                subcommand = parts[1] if len(parts) > 1 else ""
                action = parts[2] if len(parts) > 2 else ""
                flags = [p for p in parts if p.startswith('-') or p.startswith('--')]
                
                output_format = 'text'
                line_lower = line.lower()
                for flag, fmt in output_format_patterns.items():
                    if flag in flags or flag in line_lower:
                        output_format = fmt
                        break
                
                chains.append(CommandChain(
                    tool=tool,
                    subcommand=subcommand,
                    action=action,
                    flags=flags,
                    output_format=output_format,
                    description=line[:100]
                ))
        
        return chains

    def get_all_nodes(self) -> Dict[str, SkillNode]:
        return self.nodes

    def get_node_vector_matrix(self) -> Tuple[List[str], np.ndarray]:
        skill_ids = list(self.nodes.keys())
        vectors = [self.nodes[sid].semantic_vector for sid in skill_ids]

        if not vectors:
            return [], np.array([])

        matrix = np.vstack(vectors)
        return skill_ids, matrix

    def compute_semantic_similarity(self, node_a: SkillNode, node_b: SkillNode) -> float:
        if node_a.semantic_vector is None or node_b.semantic_vector is None:
            return 0.0

        vec_a = node_a.semantic_vector.reshape(1, -1)
        vec_b = node_b.semantic_vector.reshape(1, -1)

        sim = cosine_similarity(vec_a, vec_b)[0][0]
        return float(sim)

    def export_graph_data(self, output_path: str):
        """Export graph data (supports the new action-node structure)."""
        graph_data = {
            'nodes': [],
            'metadata': {
                'total_nodes': len(self.nodes),
                'encoder_type': 'TF-IDF',
                'version': '2.0.0',
                'tfidf_vocab_size': len(self.tfidf_encoder.vectorizer.vocabulary_) if self.tfidf_encoder.is_fitted else 0
            }
        }

        for skill_id, node in self.nodes.items():
            node_data = {
                'skill_id': skill_id,
                'name': node.name,
                'description': node.description[:200],
                'action_count': len(node.actions),
                'actions': [
                    {
                        'action_id': action.action_id,
                        'command': f"{action.command_chain.tool} {action.command_chain.subcommand} {action.command_chain.action}",
                        'inputs': [{'name': i.name, 'type': i.param_type} for i in action.inputs],
                        'outputs': [{'name': o.name, 'type': o.param_type} for o in action.outputs],
                        'description': action.description[:100],
                        'tfidf_vector_dim': len(action.tfidf_vector) if action.tfidf_vector is not None else 0
                    }
                    for action in node.actions
                ],
                'action_verbs': node.action_verbs,
            }
            graph_data['nodes'].append(node_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Graph data exported: {output_path}")





if __name__ == '__main__':
    # Unit test
    import tempfile

    # Create a test Skill
    test_skill_content = """---
name: test-skill
description: A test skill for reading files and outputting JSON data
---

# Test Skill

This skill reads files from a directory and outputs structured JSON data.

## Usage

Input: `file_path` (string) - Path to the file
Output: `json_data` (JSON) - Parsed file content

```bash
python read_file.py --input /path/to/file --format json
```

The skill processes text files and converts them to JSON format.
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / 'test-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(test_skill_content)
        
        builder = SkillGraphBuilder()
        node = builder.parse_skill_file(str(skill_dir))
        
        assert node is not None
        assert node.name == 'test-skill'
        assert len(node.actions) > 0  # verify action nodes exist

        # Verify action node structure
        action = node.actions[0]
        assert action.command_chain is not None
        assert len(action.inputs) > 0
        assert len(action.outputs) > 0
        
        print("\n[PASS] SkillGraphBuilder unit test passed!")
        print(f"  - Action nodes: {len(node.actions)}")
        print(f"  - Action ID: {action.action_id}")
        print(f"  - Command: {action.command_chain.tool} {action.command_chain.subcommand}")
        print(f"  - Inputs: {[i.name for i in action.inputs]}")
        print(f"  - Outputs: {[o.name for o in action.outputs]}")
