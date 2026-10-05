"""Agent namespace for the shared action risk policy."""

from ..risk_engine import RISK_BY_ACTION, evaluate_action

__all__ = ["RISK_BY_ACTION", "evaluate_action"]
