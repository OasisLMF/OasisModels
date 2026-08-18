---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
---

# Inside a run: the kernel pipeline step by step

The {doc}`high-level walkthrough <run-piwind-analysis>` runs a whole analysis with one
command. This companion opens the hood: after preparing the inputs, `oasislmf model run`
generates a kernel script (`run_kernel.sh`) that streams data through the **pytools**
tools. Here we walk that pipeline one stage at a time and inspect the intermediary data.

## The generated pipeline

The core of `run_kernel.sh` is, per partition, a single streamed chain:

```bash
evepy 1 8 | gulmc --random-generator=2 --vuln-cache-size 200 -S10 -L0 -a0 \
          | tee fifo/gul_P1 \
          | fmpy -a2 > fifo/il_P1
# then, off the tee'd streams:
summarypy -t gul -1 fifo/gul_S1_summary_P1 < fifo/gul_P1
summarypy -t il  -1 fifo/il_S1_summary_P1  < fifo/il_P1
eltpy -E bin -s work/kat/gul_S1_elt_sample_P1 < fifo/gul_S1_selt_ord_P1
```

The real script runs this across **8 partitions** in parallel, connected by named
pipes (`fifo/...`), with `modelpy` serving model data and `kat` concatenating the
partitions at the end. Below we run the **logical single-stream** version to files so we
can look at what flows between the tools.

```{note}
Runnable cells below load **committed samples** produced by running each pytools tool
once (a single event); the engine is **not** run at docs-build time. The `bash` blocks
show the actual commands. To reproduce, run them yourself in a run directory.
```

```{code-cell} python
from pathlib import Path
import pandas as pd

_c = [Path("data/pipeline"), Path("tutorials/data/pipeline"),
      Path("docs/source/tutorials/data/pipeline")]
DATA = next((c for c in _c if c.exists()), None)
assert DATA is not None, "pipeline sample data not found"
```

## Stage 1 — events (`evepy`)

`evepy` emits a partition of event ids to process (`evepy <p> <N>` = partition *p* of
*N*). It's the entry point of the stream.

```bash
evepy 1 1 -o events.bin        # all events, single partition
```

```{code-cell} python
pd.read_csv(DATA / "events.csv").head()
```

## Stage 2 — ground-up loss (`gulmc`)

`gulmc` (ground-up Monte-Carlo) reads the model data (footprint, vulnerability, …) from
the run directory and, for each item and event, samples `S` ground-up losses.

```bash
gulmc --run-dir . -S10 -a0 -i events.bin -o gul.bin
```

The GUL stream is **item-level**, keyed by `event_id, item_id, sidx, loss`. Negative
`sidx` values are special statistics, positive ones are the actual loss samples
(`1..S`); loss-free samples are dropped (`-L0` threshold):

| `sidx` | meaning |
|-------:|---------|
| -1 | numerical mean |
| -2 | standard deviation |
| -3 | impacted exposure |
| -4 | chance of loss |
| -5 | max loss |
| ≥ 1 | sample number |

```{code-cell} python
gul = pd.read_csv(DATA / "gul_stream_sample.csv")   # one item's rows
gul
```

## Stage 3 — insured loss (`fmpy`)

`fmpy` (the Financial Module) applies the policy terms — the financial structure built
into the run's `input/` — to the ground-up stream, producing insured losses.

```bash
fmpy -a2 -i gul.bin -o il.bin        # back-allocation rule 2
```

The stream keeps the same shape but is now keyed by `output_id`, and the losses are
reduced by deductibles/limits. Compare the mean (`sidx = -1`) with the ground-up value
above:

```{code-cell} python
il = pd.read_csv(DATA / "il_stream_sample.csv")
il
```

## Stage 4 — summary & ORD outputs (`summarypy` → `eltpy` / `pltpy` / `lecpy` / `aalpy`)

The loss streams are aggregated to the reporting **summary level** by `summarypy`, then
turned into ORD result tables by the output tools:

```bash
summarypy -t gul -1 gul_summary.bin < gul.bin      # aggregate to summary level
eltpy  -E bin -s gul_S1_elt_sample  < gul_S1_selt_ord   # event loss table
# pltpy / lecpy / aalpy produce PLT / EPT / ALT similarly
```

The resulting SELT / EPT / ALT tables are exactly the outputs analysed in the
{doc}`high-level walkthrough <run-piwind-analysis>`.

## Inspecting the streams (`bintocsv`)

The binary streams above were turned into the CSVs shown here with the `bintocsv`
converter (one sub-command per stream type):

```bash
bintocsv eve -i events.bin -o events.csv
bintocsv gul -i gul.bin    -o gul.csv
bintocsv fm  -i il.bin     -o il.csv
```

## Where next

- The **kernel component and stream-format reference** in the OasisLMF docs
  (`reference/kernel` — CoreComponents, Specification) documents each tool and the
  binary stream layouts in full.
- The {doc}`high-level walkthrough <run-piwind-analysis>` shows the ORD outputs this
  pipeline produces.
