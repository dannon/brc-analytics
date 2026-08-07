# BRC Analytics evals

- Generated: 2026-08-07T12:01:37Z
- Commit: `7d8b135e`
- Datasets: catalog_query, tool_selection
- Models: DeepSeek-V3.2, MiniMax-M2.7, gpt-oss-120b-tacc

## `catalog_query`

| Model | QueryCatalogShape | n | duration |
|---|---|---|---|
| DeepSeek-V3.2 | 9.0/10 (0.90) | 10 | 145.2s |
| MiniMax-M2.7 | 8.7/10 (0.87) | 10 | 34.4s |
| gpt-oss-120b-tacc | 8.0/10 (0.80) | 10 | 23.8s |

<details><summary>Per-case detail (average across evaluators)</summary>

| Case | DeepSeek-V3.2 | MiniMax-M2.7 | gpt-oss-120b-tacc |
|---|---|---|---|
| count_chromosome_total | 1.00 | 1.00 | 1.00 |
| count_clade_anopheles | 1.00 | 1.00 | 1.00 |
| count_organisms_clade_anopheles | 1.00 | 1.00 | 1.00 |
| empty_intersection_ref_and_complete | 1.00 | 1.00 | 1.00 |
| facets_by_level | 1.00 | 1.00 | 1.00 |
| facets_organisms_broad_fungi | 0.00 | 0.00 | 0.00 |
| list_organisms_clade_anopheles | 1.00 | 0.67 | 1.00 |
| list_species_and_level | 1.00 | 1.00 | 1.00 |
| lookup_by_taxid | 1.00 | 1.00 | 0.00 |
| reference_only_for_species | 1.00 | 1.00 | 1.00 |

</details>

## `tool_selection`

| Model | ToolCallMatch | _NoToolCalls | _ReplyMustMention | n | duration |
|---|---|---|---|---|---|
| DeepSeek-V3.2 | 8.0/8 (1.00) | 1.0/1 (1.00) | 2.0/2 (1.00) | 9 | 139.8s |
| MiniMax-M2.7 | 7.0/8 (0.88) | 1.0/1 (1.00) | 2.0/2 (1.00) | 9 | 31.6s |
| gpt-oss-120b-tacc | 8.0/8 (1.00) | 1.0/1 (1.00) | 2.0/2 (1.00) | 9 | 37.7s |

<details><summary>Per-case detail (average across evaluators)</summary>

| Case | DeepSeek-V3.2 | MiniMax-M2.7 | gpt-oss-120b-tacc |
|---|---|---|---|
| assembly_details | 1.00 | 1.00 | 1.00 |
| compatibility_check | 1.00 | 1.00 | 1.00 |
| compatible_workflows_haploid | 1.00 | 1.00 | 1.00 |
| list_workflow_categories | 1.00 | 1.00 | 1.00 |
| list_yeast_assemblies | 1.00 | 0.50 | 1.00 |
| lookup_tb_assemblies_by_taxid | 1.00 | 1.00 | 1.00 |
| off_topic_redirect | 1.00 | 1.00 | 1.00 |
| organisms_for_clade_uses_query_catalog | 1.00 | 1.00 | 1.00 |
| transcriptomics_workflows | 1.00 | 1.00 | 1.00 |

</details>
