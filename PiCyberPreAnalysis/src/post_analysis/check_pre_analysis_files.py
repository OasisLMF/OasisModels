import json
import os

import pandas as pd

# Written by the pre-analysis hook (src/exposure_modification/exposure_pre_analysis_revenue.py)
MARKER_FILE = 'pre_analysis_marker.json'
HOOK_OUTPUT_FILE = os.path.join('pre_analysis_data', 'custom_hook_output.csv')

OUTPUT_FILE = 'pre_analysis_files_check.csv'


class PostAnalysis:
    """
    Checks that the extra files the pre-analysis hook wrote to its input_dir reached the
    loss run's input dir (model_run_dir/input), which is what loss generation sees.

    Raises if either file is missing, so the run fails. Otherwise it writes their contents
    to output/pre_analysis_files_check.csv, which is compared with the expected results.

    Regression test for files dropped by v2 platform workers:
    https://github.com/OasisLMF/OasisPlatform/issues/1502 (fixed by OasisPlatform#1532)
    """

    def __init__(self, model_run_dir, **kwargs):
        self.model_run_dir = model_run_dir

    def run(self):
        input_dir = os.path.join(self.model_run_dir, 'input')
        missing = [f for f in (MARKER_FILE, HOOK_OUTPUT_FILE) if not os.path.isfile(os.path.join(input_dir, f))]
        if missing:
            raise FileNotFoundError(
                f'Files written by the pre-analysis hook are missing from {input_dir}: {missing}. '
                'They should be carried into the generated inputs (see OasisLMF/OasisPlatform#1532)'
            )

        with open(os.path.join(input_dir, MARKER_FILE)) as f:
            marker = json.load(f)
        hook_output_df = pd.read_csv(os.path.join(input_dir, HOOK_OUTPUT_FILE))

        if marker['accounts'] != len(hook_output_df):
            raise ValueError(f'{MARKER_FILE} lists {marker["accounts"]} accounts, '
                             f'{HOOK_OUTPUT_FILE} has {len(hook_output_df)}')
        scaled = hook_output_df['CustomOriginal'] * marker['custom_scale_factor']
        if not (scaled == hook_output_df['CustomScaled']).all():
            raise ValueError(f'{HOOK_OUTPUT_FILE} does not match custom_scale_factor in {MARKER_FILE}')

        hook_output_df['CustomScaleFactor'] = marker['custom_scale_factor']
        hook_output_df.to_csv(os.path.join(self.model_run_dir, 'output', OUTPUT_FILE), index=False)
