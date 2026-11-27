<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# PiCyber Pre-Analysis

A copy of the [PiCyber](../PiCyber) model with an exposure pre-analysis hook, to check that pre-analysis works for account only portfolios (no location file), as used by cyber and liability models.

The hook, `src/exposure_modification/exposure_pre_analysis_revenue.py`, multiplies each account's `AnnualRevenue` by `revenue_scale_factor` (set in `tests/test_1/exposure_pre_analysis.json`). The lookup maps `AnnualRevenue` into revenue bands, so the scaled accounts can be assigned a different area peril and vulnerability.

The hook also writes two extra files to its `input_dir`: `pre_analysis_marker.json` and `pre_analysis_data/custom_hook_output.csv`. The post-analysis hook, `src/post_analysis/check_pre_analysis_files.py`, raises if either file is missing from the loss run's `input` dir, and writes their contents to `output/pre_analysis_files_check.csv`, which is checked against the expected results. This covers [OasisPlatform#1502](https://github.com/OasisLMF/OasisPlatform/issues/1502): v2 platform workers dropped these files before [OasisPlatform#1532](https://github.com/OasisLMF/OasisPlatform/pull/1532) (2.5.10).

On the platform (`docker/`), the worker uses the same hooks, with its settings in `docker/exposure_pre_analysis.json`. Keep that file the same as `tests/test_1/exposure_pre_analysis.json`.

After a run, the modified account file is in `runs/losses-<UTC timestamp>/input/account.csv`.

## Running the model

```
cd tests/test_1
oasislmf model run --config oasislmf.json
```
