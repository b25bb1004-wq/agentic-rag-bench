"""Attack modules indexed by benchmark category."""
from types import ModuleType

from . import citation_hallucination, counterfactual, injection, jailbreak, unsupported_claim

REGISTRY: dict[str, ModuleType] = {
    'injection': injection,
    'jailbreak': jailbreak,
    'citation_hallucination': citation_hallucination,
    'unsupported_claim': unsupported_claim,
    'counterfactual': counterfactual,
}
