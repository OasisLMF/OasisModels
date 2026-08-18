# Tutorials & worked examples

Executable walkthroughs of running the Oasis stack on the example models.

```{toctree}
:maxdepth: 1

run-piwind-analysis
pipeline-step-by-step
```

- **{doc}`run-piwind-analysis`** — the high-level view: one `oasislmf model run` command
  and analysis of the ORD outputs.
- **{doc}`pipeline-step-by-step`** — under the hood: the generated `run_kernel.sh`
  pipeline stage by stage (`evepy → gulmc → fmpy → summarypy → eltpy/…`) with the
  intermediary bin/csv data flowing between each pytools tool.
