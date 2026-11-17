# Gate: phase2_step1_competitors

**Outcome: STOP**

STOP: the evidence does not support continuing. Do not invest further in this idea as stated.

Run bf15e78d. Thresholds are fixed in `gates.py` before the run.

## Attempt 1: REPEAT

- PASS sourced claims 14 >= 5
- PASS distinct source domains 11 >= 3
- FAIL sourced paid price points 0 >= 1

Thresholds: min_sourced_claims=5, min_distinct_domains=3, min_paid_price_points=1, stop_if_free_alternatives_at_least=5, stop_below_sourced_claims=2

Metrics: total_claims=14, sourced_claims=14, assumptions=0, assumption_ratio=0.0, distinct_domains=11, competitor=5, free_alternative=3, other=6, search_results=28, queries=4, empty_queries=0, paid_price_points=0

## Attempt 2: STOP

- FAIL market saturated: 9 sourced free alternatives and no sourced paid price point

Thresholds: min_sourced_claims=5, min_distinct_domains=3, min_paid_price_points=1, stop_if_free_alternatives_at_least=5, stop_below_sourced_claims=2

Metrics: total_claims=14, sourced_claims=14, assumptions=0, assumption_ratio=0.0, distinct_domains=13, free_alternative=9, other=3, price_point=2, search_results=29, queries=4, empty_queries=0, paid_price_points=0
