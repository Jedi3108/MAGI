"""Decision gravity: the bar to act scales with what is at stake.

A routine, reversible call should pass on a simple majority. An irreversible or
existential one should require the whole council to agree, and should fail safe
into NO CONSENSUS when it does not. This is the MAGI principle from Evangelion —
a routine decision is a majority; a self-destruct needs unanimity — made
mechanical, and it turns the council's own uncertainty into a *safe refusal*
rather than a confidently wrong verdict.

Gravity only ever RAISES the bar. It never lets a decision through on less
agreement than the base quorum already required, so adding stakes can never make
the council less careful — only more.

Pure stdlib. No third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

ROUTINE = "ROUTINE"
SERIOUS = "SERIOUS"
GRAVE = "GRAVE"

STAKES_LEVELS = (ROUTINE, SERIOUS, GRAVE)

# Human-facing descriptions, also used by the CLI/help.
STAKES_DESCRIPTION = {
    ROUTINE: "reversible, low-cost. A simple majority decides.",
    SERIOUS: "costly or hard to reverse. Every member who takes a position must agree.",
    GRAVE: "irreversible or existential. The entire council must agree; any abstention blocks.",
}


def normalize_stakes(value: object) -> str:
    """Coerce arbitrary input to a valid stakes level, defaulting to ROUTINE."""
    text = str(value or "").strip().upper()
    return text if text in STAKES_LEVELS else ROUTINE


@dataclass(frozen=True)
class GravityRule:
    """The agreement bar a decision must clear at a given stakes level."""

    stakes: str
    # Minimum members on the winning side, expressed two ways so the rule is
    # explicit rather than buried in arithmetic.
    require_full_council_agreement: bool  # every member must be on the winning side
    forbid_dissent: bool  # no OPPOSE among those who took a position (SERIOUS+)
    block_on_abstention: bool  # any ABSTAIN prevents a decisive result (GRAVE)


GRAVITY_RULES = {
    ROUTINE: GravityRule(
        stakes=ROUTINE,
        require_full_council_agreement=False,
        forbid_dissent=False,
        block_on_abstention=False,
    ),
    SERIOUS: GravityRule(
        stakes=SERIOUS,
        require_full_council_agreement=False,
        forbid_dissent=True,
        block_on_abstention=False,
    ),
    GRAVE: GravityRule(
        stakes=GRAVE,
        require_full_council_agreement=True,
        forbid_dissent=True,
        block_on_abstention=True,
    ),
}


def rule_for(stakes: object) -> GravityRule:
    return GRAVITY_RULES[normalize_stakes(stakes)]


def gravity_threshold_note(stakes: str, council_size: int) -> str:
    """One-line explanation of what this stakes level required, for the record."""
    rule = rule_for(stakes)
    if rule.require_full_council_agreement:
        return (
            f"GRAVE: all {council_size} members had to agree with no abstentions; "
            "anything short is NO CONSENSUS."
        )
    if rule.forbid_dissent:
        return (
            "SERIOUS: a majority had to agree with no dissent among members who "
            "took a position; a single OPPOSE is NO CONSENSUS."
        )
    return "ROUTINE: a simple majority of the council decided."
