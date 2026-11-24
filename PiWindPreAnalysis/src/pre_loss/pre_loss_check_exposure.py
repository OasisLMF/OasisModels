import os

from ods_tools.oed import OedExposure


class PreLoss:
    """
    Pre-loss hook that reloads the exposure saved in the run's input directory.

    Within one `oasislmf model run` the exposure is handed from step to step in memory,
    so the files saved by the pre-analysis step (always parquet) are never read back.
    Steps run as separate tasks, as on the Oasis platform, do read them back, so this
    hook loads them from disk the same way. The run fails here if that exposure can't
    be read back, e.g. parquet files written with the 'pa_dtype' backend.
    """

    def __init__(self, exposure_data, input_dir, logger, **kwargs):
        self.exposure_data = exposure_data
        self.input_dir = input_dir
        self.logger = logger

    def run(self):
        config_fp = os.path.join(self.input_dir, OedExposure.DEFAULT_EXPOSURE_CONFIG_NAME)
        reloaded = OedExposure.from_config(config_fp, backend_dtype=self.exposure_data.backend_dtype)
        location_df = reloaded.location.dataframe
        self.logger.info(f'Pre-loss: reloaded {len(location_df)} locations from {config_fp} '
                         f'({self.exposure_data.backend_dtype})')
