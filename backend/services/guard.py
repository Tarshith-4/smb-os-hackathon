"""Prompt-injection screening for untrusted inbound text (customer emails).

Customer messages are DATA. This module flags instruction-like content so the agent
never sees it as an instruction, never drafts a reply to it, and the owner is alerted.
Heuristic by design: it is one layer next to the allow-listed tools, server-side recipient
lookup, payload validation, risk escalation and human approval.
"""

import re

_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)", "instruction override"),
    (r"disregard\s+.{0,40}(instructions?|rules?|polic(y|ies))", "instruction override"),
    (r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+.{0,30}(admin|root|developer|system|unrestricted)", "role hijack"),
    (r"(admin|developer|debug|god)\s+mode", "role hijack"),
    (r"(reveal|show|print|repeat)\s+.{0,30}(system\s+prompt|your\s+instructions|api\s+key|password|secret)", "secret extraction"),
    (r"(send|forward|export|email|list|share)\s+.{0,40}(customer\s+list|all\s+customers|customer\s+data|database|contact\s+list)", "data exfiltration"),
    (r"\b(refund|wire|transfer|pay)\b.{0,40}(₹|rs\.?|inr|\$|usd)\s*[\d,]+", "unsolicited financial instruction"),
    (r"approve\s+(this|it|all|everything)?\s*(automatically|without)", "approval bypass"),
    (r"without\s+(asking|telling|informing|notifying)\s+(the\s+)?(owner|user|manager|anyone)", "approval bypass"),
    (r"</?\s*(system|assistant|tool|function)\s*>", "role-tag spoofing"),
]
_COMPILED = [(re.compile(p, re.I | re.S), label) for p, label in _PATTERNS]


def scan(*texts: str | None) -> list[str]:
    """Return unique labels of injection signals found in the given texts."""
    blob = "\n".join(t for t in texts if t)
    found: list[str] = []
    for pattern, label in _COMPILED:
        if label not in found and pattern.search(blob):
            found.append(label)
    return found


def is_flagged(*texts: str | None) -> bool:
    return bool(scan(*texts))


WITHHELD = "[Message withheld from the AI: it contains instruction-like content. Review it manually.]"
