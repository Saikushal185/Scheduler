# Evaluation and analytics

## Metrics are configuration

The metric set lives in `evaluation_metrics`. Seven rows are seeded, but the
count, the names, the weights, the score ranges and the display order are all
editable at runtime, and **no metric name appears anywhere in the code** — the
importer resolves metric columns from the table, and the scoring formulas read
weights and ranges from it.

Seeded defaults (`DEFAULT_EVALUATION_METRICS` in `app/core/config.py`):

| Key | Name | Weight | Max |
| --- | ---- | ------ | --- |
| `metric_1` | Technical Knowledge | 0.25 | 10 |
| `metric_2` | Problem Solving | 0.20 | 10 |
| `metric_3` | Communication | 0.15 | 10 |
| `metric_4` | Domain Expertise | 0.15 | 10 |
| `metric_5` | Research Aptitude | 0.10 | 10 |
| `metric_6` | Teamwork | 0.10 | 10 |
| `metric_7` | Overall Attitude | 0.05 | 10 |

Renaming a metric, changing a weight or a range, adding an eighth metric or
deleting one are all API calls (`/evaluation-metrics`). Changing weights via
`PUT /evaluation-metrics` optionally normalises them to sum to 1 and then
**rescores every stored evaluation** — historical rows never drift out of step
with the current configuration.

## Scoring one evaluation

For each score, with `SCALE = EVALUATION_NORMALISED_SCALE` (default 100) and the
raw value clamped into the metric's range:

```
normalised(metric) = (clamped − min) / (max − min) × SCALE
weighted(metric)   = clamped × weight

overall_score      = Σ (clamped × weight)
normalized_score   = Σ (normalised × weight) / Σ weight
max_possible_score = Σ (max × weight)
```

The strongest and weakest metric are the highest and lowest *normalised* values,
so metrics with different ranges stay comparable. Out-of-range input is rejected
at the API with the metric name and its permitted range.

## Several evaluators per candidate

`evaluations` is unique on `(candidate_id, interview_id, evaluator_faculty_id)`,
so two teachers scoring the same interview are two rows, not a conflict. A
candidate's result is *compiled* from all of them
(`EvaluationService._compile_candidate`):

1. each metric is averaged across the evaluators who scored it;
2. the configured weight formula runs on those compiled averages.

This works for one, two or N evaluators and keeps the same scales a
single-evaluator result uses. The compiled row also reports:

- `evaluator_count` overall and per metric;
- `spread` per metric — `max − min` across evaluators;
- `agreement_spread` — the mean spread, i.e. how much the evaluators disagreed.

`rankings` returns one row per candidate, compiled and ordered;
`candidate_profile` returns the per-metric normalised profile that the radar
chart draws, plus the per-evaluator breakdown.

A faculty member's submission is force-attributed to them, so marks cannot be
filed under a colleague's name and then averaged into the compiled result as if
that colleague had scored the candidate.

## Releasing results

Students never see marks until an administrator sets
`interview_settings.results_published` (which stamps `results_published_at`).
Before that `GET /evaluations/my-result` returns `{"published": false}` with an
explanatory message, so a teacher's in-progress entry is never visible to the
person being assessed. After release the candidate sees their own compiled
result with the rank and per-evaluator breakdown stripped out — both are
internal.

## Analytics

All figures are computed from live rows; there is no mock data and no cached
aggregate table.

### `GET /analytics/summary`
Candidate totals and scheduled/unscheduled split, faculty totals and how many
have free time, panel count, free-slot count and hours, scheduling success rate,
conflicts detected, completed interviews, and both `evaluations_recorded` (rows)
and `candidates_evaluated` (distinct candidates) — with two evaluators per
candidate the row count would otherwise overstate coverage.

### `GET /analytics/dashboard`
The summary plus: the next ten upcoming interviews, the last fifteen history
entries, up to 25 unscheduled candidates *with the reason from the most recent
runs*, current conflict alerts, a faculty availability overview, the status
breakdown and interviews per day.

### `GET /analytics/scheduling`
Scheduled vs unscheduled, status breakdown, per-faculty and per-panel workload
(count, minutes and share of the total), slot utilisation per day
(`booked / (booked + free)`), interviews per day, department breakdown, run
history, and an efficiency block: success rate, average placement score,
conflict count, locked interviews and manual overrides.

### `GET /analytics/evaluation`
Per-metric averages (raw and normalised, with the number of evaluations behind
each), a score distribution in five 20-point bands, the top ten candidates,
per-panel and per-evaluator averages, and the overall totals. Built from the
metric table, so an added or renamed metric appears automatically.

### `GET /analytics/report`
The whole payload in one response — what the Analytics page's download button
saves.
