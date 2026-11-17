"""Founder approve/reject step, enforced in code.

Nothing is published, sent or spent unless `ensure_approved` passes, and only
`request_approval` can create an approval that passes it:

- The founder must type the word `approve` at an interactive terminal.
- Without a terminal (for example `docker compose up`, CI, a pipe), every
  request is REJECTED automatically. There is no auto-approve setting.
- Approvals are bound to one action string and are kept in a private registry,
  so a hand-built Approval object does not pass `ensure_approved`.
"""
from __future__ import annotations

import secrets
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from decision_log import utc_now

GATED_KINDS = ("publish", "send", "spend", "refund")

InputFn = Callable[[str], str]


class ApprovalRequired(PermissionError):
    """Raised when an outward-facing action runs without a matching founder approval."""


@dataclass(frozen=True)
class Approval:
    action: str
    kind: str
    approved: bool
    approver: Optional[str]
    reason: str
    timestamp: str
    token: str = field(repr=False)


_ISSUED: set[str] = set()


def request_approval(
    action: str,
    kind: str,
    summary: str,
    *,
    input_fn: Optional[InputFn] = None,
    approver_label: str = "founder",
    out=sys.stdout,
) -> Approval:
    """Show what is about to happen and ask the founder to approve or reject it."""
    if kind not in GATED_KINDS:
        raise ValueError(f"kind must be one of {GATED_KINDS}")
    token = secrets.token_hex(16)
    if input_fn is None:
        if not sys.stdin or not sys.stdin.isatty():
            return Approval(action, kind, False, None, "rejected: no interactive terminal for founder approval", utc_now(), token)
        input_fn = input
    bar = "=" * 72
    print(f"\n{bar}\nFOUNDER APPROVAL NEEDED ({kind.upper()}): {action}\n{bar}\n{summary}\n{bar}", file=out)
    try:
        answer = input_fn("Type 'approve' to approve, anything else rejects: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer == "approve":
        _ISSUED.add(token)
        return Approval(action, kind, True, approver_label, "approved", utc_now(), token)
    return Approval(action, kind, False, None, f"rejected by {approver_label}", utc_now(), token)


def ensure_approved(approval: Optional[Approval], action: str) -> Approval:
    """Raise ApprovalRequired unless `approval` is a genuine approval for exactly `action`."""
    if approval is None:
        raise ApprovalRequired(f"'{action}' needs founder approval")
    if not approval.approved or approval.token not in _ISSUED:
        raise ApprovalRequired(f"'{action}' was not approved")
    if approval.action != action:
        raise ApprovalRequired(f"approval is for '{approval.action}', not '{action}'")
    return approval
