# BRC Analytics evals

- Generated: 2026-08-06T14:03:28Z
- Commit: `df66266c`
- Datasets: structured_channel
- Models: DeepSeek-V3.2, MiniMax-M2.7, gpt-oss-120b-tacc

## `structured_channel`

| Model | CaptureOnChange | ExtractSuccessRate | FinalSchemaContains | IsCompleteEquals | NoLeak | ReplySuccessRate | SchemaFieldEmpty | n | duration |
|---|---|---|---|---|---|---|---|---|---|
| DeepSeek-V3.2 | 5.2/6 (0.88) | 6.0/6 (1.00) | 3.0/4 (0.75) | 5.0/6 (0.83) | 6.0/6 (1.00) | 6.0/6 (1.00) | 2.2/3 (0.75) | 6 | 271.8s |
| MiniMax-M2.7 | 4.8/6 (0.79) | 6.0/6 (1.00) | 3.0/4 (0.75) | 5.0/6 (0.83) | 6.0/6 (1.00) | 6.0/6 (1.00) | 3.0/3 (1.00) | 6 | 77.1s |
| gpt-oss-120b-tacc | 4.8/6 (0.79) | 6.0/6 (1.00) | 3.0/4 (0.75) | 5.0/6 (0.83) | 6.0/6 (1.00) | 6.0/6 (1.00) | 3.0/3 (1.00) | 6 | 49.6s |

<details><summary>Per-case detail (average across evaluators)</summary>

| Case | DeepSeek-V3.2 | MiniMax-M2.7 | gpt-oss-120b-tacc |
|---|---|---|---|
| build_decision | 0.83 | 0.83 | 0.83 |
| clear_field | 1.00 | 0.93 | 0.93 |
| complete_handoff | 0.79 | 0.79 | 0.79 |
| explore_only | 0.96 | 1.00 | 1.00 |
| offered_not_committed | 0.92 | 1.00 | 1.00 |
| switch_decision | 0.92 | 0.92 | 0.92 |

</details>
