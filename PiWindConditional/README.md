# PiWindConditional — coverage-dependency toy model

A minimal PiWind-style model that demonstrates gulmc **coverage dependency**: at each location
**Contents** (coverage type 3) is a *dependent* of **Building** (coverage type 1). The
contents' damage is driven by the building's sampled damage bin through a **conditional
(damage-transition) vulnerability**, rather than by an independent draw.

## What makes it work

- **Non-deterministic hazard.** `model_data/footprint` gives each event several intensity bins
  with probabilities (see `scripts/generate.py`), so the building's sampled intensity — and
  hence its damage — genuinely varies. (Vanilla PiWind has a deterministic footprint, where
  coverage dependency has nothing to bite on.)
- **Building** uses a normal hazard-indexed vulnerability (`vulnerability.csv`, id 1).
- **Contents** uses a **conditional vulnerability** (`conditional_vulnerability.csv`, id 100):
  a `P(contents damage bin | building damage bin)` transition matrix. Here contents track the
  building one bin lower with some spread (contents slightly less vulnerable than the structure).
- **`meta_data/model_settings.json`** declares the link:
  `coverage_dependency_settings: [{source_coverage_type: 1, dependent_coverage_type: 3}]`.
- The keys server returns Building and Contents at the **same areaperil**, which is what
  activates the dependency per location.
- `num_damage_bins` (6) > `num_intensity_bins` (4) on purpose — the conditional matrix is sized
  `num_damage_bins x num_damage_bins`, independent of the footprint's intensity resolution.

## Run

```bash
cd tests/test_1
oasislmf model run --config oasislmf.json --model-run-dir /tmp/pwc_run
```

The gulmc log shows `coverage dependency: switched ON (2 dependent coverages)`.

## Test cases

- **`tests/test_1`** — the standard case: Building **insured** (TIV > 0) driving insured Contents,
  GUL output only.
- **`tests/test_2`** — the **zero-TIV driver** case: Building **uninsured** (`BuildingTIV = 0`)
  still driving insured Contents, with **IL output enabled**. An uninsured source is retained
  purely to drive its dependent and flows as an ordinary zero-TIV, zero-loss coverage (no special
  casing). This case exercises the IL/FM path end-to-end — the FM structure must be built with the
  driver coverage present, so it is the regression guard for that scenario.

  ```bash
  cd tests/test_2
  oasislmf model run --config oasislmf.json --model-run-dir /tmp/pwc_test2
  ```

## Observed behaviour (500 samples, per location)

| coverage | mean damage fraction |
|---|---|
| Building (source) | ~0.45 |
| Contents (dependent) | ~0.40 |

Per-sample `corr(building, contents) ≈ 0.96` — contents closely track the building's realised
damage, sitting a little lower per the conditional matrix. With the dependency removed, contents
would be an independent draw and this linkage would be far weaker.

## Regenerate

```bash
python scripts/generate.py
```

Rebuilds all `model_data` files, the keys/lookup config, `meta_data/model_settings.json` and the
`tests/test_1` exposure + settings. `tests/test_2` (the zero-TIV driver case) is hand-authored and
not touched by the script.
