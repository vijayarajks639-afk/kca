"""Reuse measurement (WP-24) — quantifies, from the repository itself, how much
of the platform domain #2 reused vs rebuilt, and whether the whitepaper's
marginal-cost claim holds. The published table is docs/reuse-measurement.md.
"""

from kca.evals.reuse.measure import AreaCount, ReuseReport, measure_reuse

__all__ = ["AreaCount", "ReuseReport", "measure_reuse"]
