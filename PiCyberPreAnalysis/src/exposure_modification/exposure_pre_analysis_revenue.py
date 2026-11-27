import json
import logging
import os

# Extra files the hook writes to its input_dir (besides the exposure files). The platform
# must carry them into the generated inputs, where the post-analysis hook
# (src/post_analysis/check_pre_analysis_files.py) checks for them.
# See https://github.com/OasisLMF/OasisPlatform/pull/1532
MARKER_FILE = 'pre_analysis_marker.json'
HOOK_OUTPUT_FILE = os.path.join('pre_analysis_data', 'custom_hook_output.csv')


class ExposurePreAnalysis:
    """
    Example of custom module called by oasislmf/computation/hooks/pre_analysis.py
    for an account only (cyber) portfolio - there is no location file.

    The account's AnnualRevenue is multiplied by "revenue_scale_factor" (from
    exposure_pre_analysis.json), e.g. to bring revenues up to date. The lookup maps
    AnnualRevenue into revenue bands, so the scaled accounts can move to a different
    area peril / vulnerability.

    The hook also writes two extra files to input_dir, one at the top level and one in a
    subfolder, recording what it did. Loss generation and the post-analysis hook can read
    them from the run's input dir.
    """

    def __init__(self, exposure_data, exposure_pre_analysis_setting=None, input_dir=None, **kwargs):
        self.exposure_data = exposure_data
        self.exposure_pre_analysis_setting = exposure_pre_analysis_setting or {}
        self.input_dir = input_dir

    def run(self):
        scale_factor = self.exposure_pre_analysis_setting.get('revenue_scale_factor', 1)
        account_df = self.exposure_data.account.dataframe
        custom_original = account_df['AnnualRevenue'].copy()

        logging.info(f'Scaling AnnualRevenue by {scale_factor}')
        account_df['AnnualRevenue'] = account_df['AnnualRevenue'] * scale_factor

        self.exposure_data.account.dataframe = account_df

        if self.input_dir:
            self.write_extra_files(account_df, custom_original, scale_factor)

    def write_extra_files(self, account_df, custom_original, scale_factor):
        with open(os.path.join(self.input_dir, MARKER_FILE), 'w') as f:
            json.dump({'custom_scale_factor': scale_factor, 'accounts': len(account_df)}, f, indent=4)

        hook_output_fp = os.path.join(self.input_dir, HOOK_OUTPUT_FILE)
        os.makedirs(os.path.dirname(hook_output_fp), exist_ok=True)
        hook_output_df = account_df[['PortNumber', 'AccNumber']].copy()
        hook_output_df['CustomOriginal'] = custom_original
        hook_output_df['CustomScaled'] = account_df['AnnualRevenue']
        hook_output_df.to_csv(hook_output_fp, index=False)
