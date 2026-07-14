"""Runner lifecycle planner.

Distilled from ``exo.worker.plan`` — a pure function that, given the current
runner phase and desired target, returns the next phase to transition to. The
upstream planner also handles download/warmup priority ordering across many
runners; here we model the single-runner state machine that the Android worker
drives.
"""

from __future__ import annotations

from enum import Enum


class RunnerPhase(str, Enum):
    """States a runner moves through (distilled from ``RunnerStatus``)."""

    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    DOWNLOADING = "DOWNLOADING"
    LOADING = "LOADING"
    WARMING_UP = "WARMING_UP"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


# Ordered forward lifecycle; ``plan_next_phase`` walks it toward the target.
_FORWARD = [
    RunnerPhase.IDLE,
    RunnerPhase.CONNECTING,
    RunnerPhase.DOWNLOADING,
    RunnerPhase.LOADING,
    RunnerPhase.WARMING_UP,
    RunnerPhase.READY,
]


def plan_next_phase(
    current: RunnerPhase,
    target: RunnerPhase,
    *,
    weights_present: bool = False,
) -> RunnerPhase:
    """Return the next phase a runner should move to.

    Mirrors the priority-ordered planning of upstream ``worker/plan.py``:
    teardown takes precedence, otherwise advance one step toward ``target``,
    skipping DOWNLOADING when the shard's weights are already present.
    """
    if target in (RunnerPhase.STOPPING, RunnerPhase.STOPPED):
        if current == RunnerPhase.STOPPED:
            return RunnerPhase.STOPPED
        return RunnerPhase.STOPPING if current != RunnerPhase.STOPPING else RunnerPhase.STOPPED

    if current == RunnerPhase.RUNNING:
        return RunnerPhase.RUNNING

    if current == RunnerPhase.READY:
        return RunnerPhase.RUNNING if target == RunnerPhase.RUNNING else RunnerPhase.READY

    # Advance one step along the forward lifecycle.
    try:
        idx = _FORWARD.index(current)
    except ValueError:
        return RunnerPhase.IDLE
    nxt = _FORWARD[min(idx + 1, len(_FORWARD) - 1)]
    if nxt == RunnerPhase.DOWNLOADING and weights_present:
        return RunnerPhase.LOADING
    return nxt
