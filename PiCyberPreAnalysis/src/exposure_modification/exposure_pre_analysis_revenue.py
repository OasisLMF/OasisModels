import logging


class ExposurePreAnalysis:
    """
    Example of custom module called by oasislmf/computation/hooks/pre_analysis.py
    for an account only (cyber) portfolio - there is no location file.

    The account's AnnualRevenue is multiplied by "revenue_scale_factor" (from
    exposure_pre_analysis.json), e.g. to bring revenues up to date. The lookup maps
    AnnualRevenue into revenue bands, so the scaled accounts can move to a different
    area peril / vulnerability.
    """

    def __init__(self, exposure_data, exposure_pre_analysis_setting, **kwargs):
        self.exposure_data = exposure_data
        self.exposure_pre_analysis_setting = exposure_pre_analysis_setting

    def run(self):
        scale_factor = self.exposure_pre_analysis_setting.get('revenue_scale_factor', 1)
        account_df = self.exposure_data.account.dataframe

        logging.info(f'Scaling AnnualRevenue by {scale_factor}')
        account_df['AnnualRevenue'] = account_df['AnnualRevenue'] * scale_factor

        self.exposure_data.account.dataframe = account_df
