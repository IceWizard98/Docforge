"""Confidence bucketing for retrieval scores.

Retrieval emits RRF/rerank scores that are not calibrated probabilities, so we
collapse a (typically normalized) score into three coarse buckets. Conservative
by design — only ``high`` counts as a confidently-filled slot — because for
contracts a wrongly-"filled" slot risks a hallucinated clause.
"""

from typing import Literal

Bucket = Literal["high", "medium", "low"]

DEFAULT_HIGH = 0.66
DEFAULT_MEDIUM = 0.33


def bucket(
    score: float, high: float = DEFAULT_HIGH, medium: float = DEFAULT_MEDIUM
) -> Bucket:
    """Map a score to high/medium/low. Scores are expected normalized to 0..1."""
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    return "low"
