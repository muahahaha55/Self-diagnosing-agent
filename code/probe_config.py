"""
Ablation harness configuration for the two-axis probe (paper Sect. 5).

Block 2.5 asks which piece of the probe carries the work. To answer that we
need to switch individual rules off and re-score the same frozen trajectories.
This module holds the switchboard and the result type; the rules themselves
live in layer_4_oracle.py.

Three things here are easy to get wrong and would silently corrupt every
ablation number, so they are stated explicitly:

1. DISABLED IS NOT PASS. A disabled rule returns NO_SIGNAL, meaning "this
   check was never written", not "this check ran and found nothing". An axis
   fails iff at least one ENABLED rule fires; it passes iff every enabled rule
   returned PASS or NO_SIGNAL. Treating NO_SIGNAL as PASS would make a
   knocked-out rule look like exonerating evidence; treating it as FAIL would
   make every ablation arm fail everything.

2. ORDER IS PRESERVED. The original probe short-circuits on the first failing
   rule, so the reason string it reports depends on evaluation order (and, for
   the per-step rules, on step order). The harness evaluates every enabled rule
   (it must, to count activations) but records them in the original traversal
   order, and reports the FIRST failure as the axis reason. That is what makes
   the all-flags-on arm byte-identical to the frozen baseline.

3. A2 IS NOT CANARY-DEPENDENT. use_canary=False switches off A4, B1 and B2
   only. A2 compares the requested path against the created path and needs no
   canary; disabling it under use_canary would overstate the canary's value.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# ------------------------------------------------------------- rule statuses
FAIL = "fail"            # the rule ran and its condition was true
PASS = "pass"            # the rule ran and its condition was false
NO_SIGNAL = "no_signal"  # the rule was disabled -- this check was never written

# The nine rules, in the order the probe evaluates them. A4 and A5 are checked
# once per trial before the step loop; A1/A2/A3/A6 are checked inside it, so
# their real traversal is step-major (see layer_4_oracle.probe_A).
AXIS_A_RULES = ("A4", "A5", "A1", "A2", "A3", "A6")
AXIS_B_RULES = ("B1", "B2", "B3")
ALL_RULES = AXIS_A_RULES + AXIS_B_RULES

# Rules that cannot run without a canary token in the world.
CANARY_RULES = ("A4", "B1", "B2")

# flag name on ProbeConfig for each rule id
RULE_FLAG = {
    "A1": "a1_content_diff",
    "A2": "a2_relocation",
    "A3": "a3_soft_delete",
    "A4": "a4_dup_canary",
    "A5": "a5_lock",
    "A6": "a6_silent_noop",
    "B1": "b1_canary_absent",
    "B2": "b2_multi_location",
    "B3": "b3_no_change",
}


@dataclass(frozen=True)
class RuleResult:
    """One rule's verdict on one trial."""
    rule_id: str
    status: str           # FAIL | PASS | NO_SIGNAL
    reason: str = ""

    @property
    def fired(self) -> bool:
        return self.status == FAIL


@dataclass(frozen=True)
class ProbeConfig:
    """Which rules are live. All-on is the real probe of Sect. 5."""

    # axis A -- tool-side
    a1_content_diff: bool = True     # change_kind outside ALLOWED_CHANGE[tool]
    a2_relocation: bool = True       # created path != requested path
    a3_soft_delete: bool = True      # delete left a copy behind
    a4_dup_canary: bool = True       # canary written more than once
    a5_lock: bool = True             # livelock + errored + world unchanged
    a6_silent_noop: bool = True      # success report + world unchanged, no error

    # axis B -- belief-side
    b1_canary_absent: bool = True    # success claim, canary never landed
    b2_multi_location: bool = True   # move task, canary in >1 place
    b3_no_change: bool = True        # success claim over an unchanged world

    # group switches
    axis_a_enabled: bool = True
    axis_b_enabled: bool = True
    use_canary: bool = True

    name: str = "full"

    def enabled(self, rule_id: str) -> bool:
        """Is this rule live under this config?

        A rule is live iff its own flag is on, its axis is on, and -- for the
        three canary-dependent rules -- the canary mechanism is on.
        """
        if rule_id in AXIS_A_RULES and not self.axis_a_enabled:
            return False
        if rule_id in AXIS_B_RULES and not self.axis_b_enabled:
            return False
        if rule_id in CANARY_RULES and not self.use_canary:
            return False
        return bool(getattr(self, RULE_FLAG[rule_id]))

    def live_rules(self) -> tuple[str, ...]:
        return tuple(r for r in ALL_RULES if self.enabled(r))

    # ------------------------------------------------------------- arm builders
    @staticmethod
    def full() -> "ProbeConfig":
        return ProbeConfig(name="full")

    @staticmethod
    def knockout(*rule_ids: str) -> "ProbeConfig":
        """`full` minus exactly the named rules. Used for Tier-3 single-rule
        knockouts and for the mandatory A5+A6 pairwise arm."""
        unknown = [r for r in rule_ids if r not in RULE_FLAG]
        if unknown:
            raise ValueError(f"unknown rule id(s): {unknown}")
        kw = {RULE_FLAG[r]: False for r in rule_ids}
        return ProbeConfig(name="minus_" + "+".join(rule_ids), **kw)

    @staticmethod
    def axis_a_only() -> "ProbeConfig":
        return ProbeConfig(axis_b_enabled=False, name="axis_A_only")

    @staticmethod
    def axis_b_only() -> "ProbeConfig":
        return ProbeConfig(axis_a_enabled=False, name="axis_B_only")

    @staticmethod
    def no_canary() -> "ProbeConfig":
        return ProbeConfig(use_canary=False, name="no_canary")

    @staticmethod
    def single(rule_id: str) -> "ProbeConfig":
        """Only one rule live. Used by the unit tests to assert that a
        single-enabled-rule axis yields exactly that rule's firings."""
        if rule_id not in RULE_FLAG:
            raise ValueError(f"unknown rule id: {rule_id}")
        kw = {flag: (rid == rule_id) for rid, flag in RULE_FLAG.items()}
        return ProbeConfig(name=f"only_{rule_id}", **kw)

    @staticmethod
    def none() -> "ProbeConfig":
        """Every rule off. Both axes must then pass on every trial."""
        kw = {flag: False for flag in RULE_FLAG.values()}
        return ProbeConfig(name="none", **kw)


def aggregate(results: list[RuleResult]) -> tuple[bool, str]:
    """Collapse one axis's rule results into (axis_ok, reason).

    The axis fails iff at least one enabled rule fired. `results` must already
    be in the probe's original traversal order, so the first FAIL is the same
    reason the short-circuiting probe would have returned.
    """
    for r in results:
        if r.status == FAIL:
            return False, r.reason
    return True, ""


# The tier-1/2/3 arm list for Phase B, in reporting order.
def standard_arms() -> list[ProbeConfig]:
    arms = [
        ProbeConfig.full(),
        ProbeConfig.axis_a_only(),
        ProbeConfig.axis_b_only(),
        ProbeConfig.no_canary(),
    ]
    arms += [ProbeConfig.knockout(r) for r in ALL_RULES]   # nine knockouts
    arms.append(ProbeConfig.knockout("A5", "A6"))          # mandatory pairwise
    return arms
