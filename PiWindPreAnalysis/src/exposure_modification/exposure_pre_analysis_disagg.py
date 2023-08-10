import pandas as pd

class ExposurePreAnalysis:
    """
    Example of custom module called by oasislmf/model_preparation/ExposurePreAnalysis.py

    put something about the process in here...
    """

    def __init__(self, exposure_data, exposure_pre_analysis_setting, **kwargs):
        self.exposure_data = exposure_data
        self.exposure_pre_analysis_setting = exposure_pre_analysis_setting

    def run(self):
        # load exposure object into dataframe
        location_df = self.exposure_data.location.dataframe

        # get API details
        api_url = self.exposure_pre_analysis_setting['API_URL']
        api_key = self.exposure_pre_analysis_setting['API_Key']

        # call api

        ### do the api call here ###

        # update lat/longs where missing

        ### replace with your logic ###
        location_df['Latitude'] = location_df['Latitude'].fillna(1.234567)
        location_df['Longitude'] = location_df['Longitude'].fillna(2.345678)

        # write back updated dataframe to exposure object
        self.exposure_data.location.dataframe = location_df
