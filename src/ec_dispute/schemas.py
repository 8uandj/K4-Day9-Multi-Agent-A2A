"""DEPRECATED shim — the contracts moved to ``ec_dispute.contracts``.

Kept so code written against ``ec_dispute.schemas`` keeps importing cleanly. New code should
use::

    from ec_dispute.contracts import CandidateOutput, A2AEnvelope

Split rationale: ``contracts/output_schema.py`` holds what the grader reads,
``contracts/envelope.py`` holds what agents pass between themselves. Keeping them apart
means A5/A6 can be given the output schema without also handing them transport internals.
"""

from ec_dispute.contracts import *  # noqa: F401,F403
from ec_dispute.contracts import __all__ as _contract_names

__all__ = list(_contract_names)
