from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.domain.activity import ActivitySnapshot


@dataclass(frozen=True, slots=True)
class DuplicateScore:
    total: float
    temporal_overlap: float
    start_similarity: float
    duration_similarity: float
    sport_match: float
    power_similarity: float
    hr_similarity: float
    cadence_similarity: float
    source_diversity: float


WEIGHTS = {
    "temporal_overlap": 0.35,
    "start_similarity": 0.20,
    "duration_similarity": 0.15,
    "sport_match": 0.05,
    "power_similarity": 0.10,
    "hr_similarity": 0.05,
    "cadence_similarity": 0.05,
    "source_diversity": 0.05,
}


def _similarity(a: float | None, b: float | None, tolerance_ratio: float) -> float:
    if a is None or b is None:
        return 0.5  # unknown is neutral, not evidence against duplication
    denom = max(abs(a), abs(b), 1.0)
    relative_error = abs(a - b) / denom
    return max(0.0, 1.0 - relative_error / tolerance_ratio)


def _start_similarity(a: ActivitySnapshot, b: ActivitySnapshot) -> float:
    delta = abs((a.start_at - b.start_at).total_seconds())
    return max(0.0, 1.0 - delta / 300.0)  # zero after 5 min


def _temporal_overlap(a: ActivitySnapshot, b: ActivitySnapshot) -> float:
    if a.duration_s is None or b.duration_s is None or a.end_at is None or b.end_at is None:
        return 0.5
    latest_start = max(a.start_at, b.start_at)
    earliest_end = min(a.end_at, b.end_at)
    overlap = max(0.0, (earliest_end - latest_start).total_seconds())
    return min(1.0, overlap / max(1.0, min(a.duration_s, b.duration_s)))


def _norm_source(source: str | None) -> str:
    return (source or "unknown").strip().lower()


def score_duplicate(a: ActivitySnapshot, b: ActivitySnapshot) -> DuplicateScore:
    temporal_overlap = _temporal_overlap(a, b)
    start_similarity = _start_similarity(a, b)
    duration_similarity = _similarity(a.duration_s, b.duration_s, 0.08)
    sport_match = 1.0 if a.sport.lower() == b.sport.lower() else 0.0
    power_similarity = _similarity(a.avg_power_w, b.avg_power_w, 0.15)
    hr_similarity = _similarity(a.avg_hr_bpm, b.avg_hr_bpm, 0.12)
    cadence_similarity = _similarity(a.avg_cadence_rpm, b.avg_cadence_rpm, 0.12)
    source_diversity = 1.0 if _norm_source(a.recording_source) != _norm_source(b.recording_source) else 0.4

    components = locals()
    total = sum(components[name] * weight for name, weight in WEIGHTS.items())
    return DuplicateScore(total=min(1.0, total), **{name: components[name] for name in WEIGHTS})


def candidate_pairs(activities: list[ActivitySnapshot]) -> list[tuple[int, int, DuplicateScore]]:
    out: list[tuple[int, int, DuplicateScore]] = []
    ordered = sorted(enumerate(activities), key=lambda item: item[1].start_at)
    for pos, (i, a) in enumerate(ordered):
        for j, b in ordered[pos + 1 :]:
            if b.start_at - a.start_at > timedelta(hours=6):
                break
            if a.sport.lower() != b.sport.lower():
                continue
            score = score_duplicate(a, b)
            out.append((i, j, score))
    return out


def build_groups(activities: list[ActivitySnapshot], auto_merge_threshold: float = 0.90) -> list[list[int]]:
    parent = list(range(len(activities)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, j, score in candidate_pairs(activities):
        if score.total >= auto_merge_threshold:
            union(i, j)

    groups: dict[int, list[int]] = {}
    for idx in range(len(activities)):
        groups.setdefault(find(idx), []).append(idx)
    return list(groups.values())
