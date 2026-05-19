"""Deterministic tuning state machine and candidate generation."""

from __future__ import annotations

import itertools
import random
from enum import StrEnum

from pydantic import BaseModel, Field, ValidationError

from inflab.schemas import FrameworkParams


class AgentPhase(StrEnum):
    observe = "Observe"
    plan = "Plan"
    validate = "Validate"
    act = "Act"
    collect = "Collect"
    reflect = "Reflect"
    done = "Done"


class CandidateSet(BaseModel):
    candidates: list[FrameworkParams] = Field(default_factory=list)


def rule_baseline(gpu_count: int = 1) -> FrameworkParams:
    return FrameworkParams(
        tensor_parallel_size=max(gpu_count, 1),
        gpu_memory_utilization=0.88,
        max_num_seqs=128,
        max_num_batched_tokens=8192,
    )


def grid_search() -> list[FrameworkParams]:
    candidates = []
    for memory, seqs in itertools.product([0.82, 0.9], [64, 128]):
        candidates.append(FrameworkParams(gpu_memory_utilization=memory, max_num_seqs=seqs))
    return candidates


def random_search(seed: int = 7, count: int = 2) -> list[FrameworkParams]:
    rng = random.Random(seed)
    return [
        FrameworkParams(
            gpu_memory_utilization=round(rng.uniform(0.78, 0.93), 2),
            max_num_seqs=rng.choice([64, 96, 128, 160]),
        )
        for _ in range(count)
    ]


class MockLLMCandidateProvider:
    def generate(self, context: dict[str, object]) -> CandidateSet:
        raw = {
            "candidates": [
                {
                    "gpu_memory_utilization": 0.86,
                    "max_num_seqs": 96,
                    "max_num_batched_tokens": 6144,
                }
            ]
        }
        return CandidateSet.model_validate(raw)


def heuristic_prune(candidates: list[FrameworkParams]) -> list[FrameworkParams]:
    return [
        candidate
        for candidate in candidates
        if candidate.max_num_seqs * candidate.max_model_len <= 1_048_576
        and candidate.gpu_memory_utilization <= 0.94
    ]


def plan_candidates(
    gpu_count: int = 1, max_trials: int = 2
) -> tuple[list[AgentPhase], list[FrameworkParams]]:
    phases = [
        AgentPhase.observe,
        AgentPhase.plan,
        AgentPhase.validate,
        AgentPhase.act,
        AgentPhase.collect,
        AgentPhase.reflect,
        AgentPhase.done,
    ]
    provider = MockLLMCandidateProvider()
    candidates = [
        rule_baseline(gpu_count),
        *grid_search(),
        *random_search(),
        *provider.generate({}).candidates,
    ]
    valid: list[FrameworkParams] = []
    for candidate in candidates:
        try:
            valid.append(FrameworkParams.model_validate(candidate.model_dump()))
        except ValidationError:
            continue
    return phases, heuristic_prune(valid)[:max_trials]
