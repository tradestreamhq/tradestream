---
name: "recommend-retirement"
description: "Make nuanced strategy retirement decisions by weighing edge cases like seasonal performance, market regime changes, and recent parameter updates. Use when a strategy passes initial performance evaluation but needs contextual judgment before retirement."
---

# Recommend Retirement

Apply contextual judgment to strategies flagged by evaluate-performance. A strategy that fails thresholds may still deserve a reprieve based on edge cases — this skill makes that call.

## When to Use

After evaluate-performance flags a strategy as a retirement candidate. This skill adds nuance before the final retire/keep decision.

## Edge Case Evaluation

For each candidate, assess these factors before recommending retirement:

| Edge Case | Check | Action if True |
|-----------|-------|----------------|
| **Seasonal strategy** | Does the strategy historically underperform in the current season/quarter? | Defer retirement — re-evaluate after season ends |
| **Market regime change** | Has the broader market shifted regime (bull→bear, low→high vol) recently? | Defer retirement — strategy may recover when regime normalizes |
| **Recent parameter update** | Were strategy parameters changed within the last 3 months? | Defer retirement — insufficient data to judge new parameters |
| **Symbol mismatch** | Does the strategy perform well on other symbols but poorly on this one? | Recommend symbol reassignment instead of retirement |
| **Correlated failures** | Are multiple strategies failing simultaneously? | Flag as systemic — likely market-driven, not strategy-specific |

## Workflow

1. **Review evaluation data**: Read the retirement candidate list from evaluate-performance
2. **Check each edge case**: For every candidate, assess all five edge cases above
3. **Apply judgment**: If any edge case applies, defer retirement with a documented reason and re-evaluation date
4. **Final decision**: For candidates with no applicable edge cases, recommend retirement via soft delete (`status='RETIRED'`)
5. **Document reasoning**: Include per-candidate reasoning covering which edge cases were checked and why the decision was made

## Output

Return a final retirement decision for each candidate:
- **RETIRE**: No edge cases apply — proceed with soft delete and log reasoning
- **DEFER**: Edge case applies — specify which one and set re-evaluation date
- **REASSIGN**: Strategy works on other symbols — recommend reassignment instead
