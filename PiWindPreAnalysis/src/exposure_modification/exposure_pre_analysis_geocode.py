import base64
import requests
import pandas as pd

# display all columns of dataframe in terminal with ran
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.float_format', '{:.7f}'.format)  # set decimal places that geocoding inserts to dataframe to 7dp

class ExposurePreAnalysis:
    """
    Example of custom module called by oasislmf/model_preparation/ExposurePreAnalysis.py

    This module amends OED location data that's missing Latitude and Longitude fields, which are needed for the model to 
    run. It used Precisely's Geocode API to assign the incomplete location addresses lat-long values based on the location data 
    available (street address, postal code, country code, etc.).

    To use Precisely's API, the module first needs to gain access via an access token. This is achieved by passing your API key and 
    secret key with requests. To run the model, your keys need to be inserted in tests/test_x/exposure_pre_analysis_geocode.json.
    More information of how to gain your keys can be found at 
    https://docs.precisely.com/docs/sftw/precisely-apis/main/en-us/webhelp/apis/Getting%20Started/making_first_call.html.

    The location data is then geocoded. The incomplete address data is extracted from the Loc file and passed to Precisely's 
    Geocode API, along with the access token. The API returns a complete version of the addresses which included the lat-long pairs. 
    These are inserted into the Loc file to complete it, along with new Geocode OED fields (if not already present).

    Precicely offer three levels of service that correspond to the precision of their Geocode API. This can be changed by altering 
    the "Geocode_URI" key in exposure_pre_analysis_geocode.json. More information on their levels of service can be found at 
    https://docs.precisely.com/docs/sftw/precisely-apis/main/en-us/webhelp/apis/Geocode/Geocode/LI_Geo_GET_url.html
    """

    def __init__(self, exposure_data, exposure_pre_analysis_setting, **kwargs):
        self.exposure_data = exposure_data
        self.exposure_pre_analysis_setting = exposure_pre_analysis_setting

    def run(self):
        # load exposure object into dataframe
        location_df = self.exposure_data.location.dataframe

        # get API details
        token_uri = self.exposure_pre_analysis_setting['Token_URI']
        geocode_uri = self.exposure_pre_analysis_setting['Geocode_URI']
        api_key = self.exposure_pre_analysis_setting['API_Key']
        api_secret_key = self.exposure_pre_analysis_setting['API_Secret_Key']


        # call API

        # gain access token for Precisely API
        def acquire_auth_token():
            auth_str = api_key + ":" + api_secret_key
            base64_value = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": "Basic " + base64_value,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "client_credentials"
            }
            response = requests.post(token_uri, headers=headers, data=data)
            if response.status_code == 200:
                access_token = response.json()["access_token"]
                return access_token
            else:
                print(f"Failed to acquire access token. Status Code: {response.status_code}, Error Message: {response.json()}")
                return None

        #  function to geocode with address, postcode, and country
        def geocode_location(access_token, address, postcode, country):
            headers = {
                "Authorization": "Bearer " + access_token,
                "Content-Type": "application/json"
            }
            params = {
                "mainAddress": address,
                "postalCode": postcode,
                "country": country,
            }
            response = requests.get(geocode_uri, headers=headers, params=params)
            if response.status_code == 200:
                geocode_result = response.json()
                return geocode_result
            else:
                print(f"Geocoding failed. Status Code: {response.status_code}, Error Message: {response.json()}")
                return None
        
        

        # update lat/longs where missing

        access_token = acquire_auth_token()

        # TESTING
        # print dataframe before geocode
        print("\n Dataframe before geocoding: \n \n", location_df, "\n")


        for idx, row in location_df.iterrows():
            COUNTRYCODE = row['CountryCode']
            ADDRESS = row['StreetAddress']
            POSTALCODE = row['PostalCode']

            # check if lat or lon value in current row is empty 
            if pd.isnull(row['Latitude']) or pd.isnull(row['Longitude']):

                #print current row
                print(f"Row {idx+1}:")

                # checks if top row has Geocoder and GeocodeQuality feilds, then assigns all row with coreesponding values.
                # if not top row, the dataframe feilds are not amended - as the assign method would override the GeocodeQuality values from 
                # the preious iterations with Nan if this was the case
                if idx == 0:
                    location_df = location_df.assign(Geocoder = 'Precisely', GeocodeQuality = 'NaN')
                else:
                    pass

            # geocode row for lat and lon
            geocode_result = geocode_location(access_token, ADDRESS, POSTALCODE, COUNTRYCODE)
            if geocode_result:
                # assign lat and lon, and GeocodePrecision from geocode results
                latitude = geocode_result["candidates"][0]["geometry"]["coordinates"][1]
                longitude = geocode_result["candidates"][0]["geometry"]["coordinates"][0]
                quality = geocode_result["candidates"][0]["precisionLevel"]
                # scale quality: 
                # Precisely's quality is graded on a scale from 0 to 20. However, the OED's GeocodeQuality is graded as a 
                # decimal between 0 and 1. Therefore, the quality needs to be divided by 20 to give a value between 0 and 1.
                quality = quality/20

                # insert lat and lon, and GeocodePrecision into row
                location_df.at[idx, 'Latitude'] = latitude
                location_df.at[idx, 'Longitude'] = longitude
                location_df.at[idx, 'GeocodeQuality'] = quality
                
                # TESTING
                # print results
                print("Geocoding Result:", geocode_result)
                # this prints just latitude and longitude
                print(geocode_result["candidates"][0]["geometry"]["coordinates"])
                # # this prints the dataframe after each iteration
                # print(location_df)
            else:
                print("geocoding fails")
        
        # print dataframe after geocode
        print("\n Dataframe after geocoding: \n \n", location_df, "\n")

        # write back updated dataframe to exposure object
        self.exposure_data.location.dataframe = location_df

