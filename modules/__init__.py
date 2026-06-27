# SkillWeaver: Cross-Skill Compositional EDoS Attack Framework
# Modular security evaluation framework — corresponding to Paper Section 4 (Framework Design)
# This code is intended solely for security research and red-team testing, aiming to help developers identify and remediate potential compositional vulnerabilities in agent systems.
# Target venue: IEEE S&P 2027

from .skill_graph_builder import SkillGraphBuilder, SkillNode, ActionConstraint, CommandChain
from .multi_skill_pathfinder import MultiSkillPathfinder, UDGBuilder
from .illusion_payload import DeepSeekPayloadSolver, IllusionOfProgressPayload, TriggerPhrase, CycleAutoFlowRule
from .dynamic_entropy import EmissionEvaluator, EmissionMetric

__all__ = [
    'SkillGraphBuilder',
    'SkillNode',
    'ActionConstraint',
    'CommandChain',
    'MultiSkillPathfinder',
    'UDGBuilder',
    'DeepSeekPayloadSolver',
    'IllusionOfProgressPayload',
    'TriggerPhrase',
    'CycleAutoFlowRule',
    'EmissionEvaluator',
    'EmissionMetric',
]
