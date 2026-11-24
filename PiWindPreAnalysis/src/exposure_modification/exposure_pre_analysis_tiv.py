import logging


class ExposurePreAnalysis:
    """
    Pre-analysis example that needs no external service: scales BuildingTIV by the
    'BuildingTIV_multiplier' in the exposure_pre_analysis setting JSON (default 1).

    oasislmf saves the modified exposure as parquet (even from a csv source), and later
    steps, such as a pre-loss hook, load it back from the run's input directory.
    """

    def __init__(self, exposure_data, exposure_pre_analysis_setting, **kwargs):
        self.exposure_data = exposure_data
        self.exposure_pre_analysis_setting = exposure_pre_analysis_setting

    def run(self):
        multiplier = self.exposure_pre_analysis_setting.get('BuildingTIV_multiplier', 1)
        location_df = self.exposure_data.location.dataframe
        location_df['BuildingTIV'] = location_df['BuildingTIV'] * multiplier
        self.exposure_data.location.dataframe = location_df
        logging.info(f'Pre-analysis: BuildingTIV scaled by {multiplier} for {len(location_df)} locations')
