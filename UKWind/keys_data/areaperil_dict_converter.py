
from shapely.geometry import Point
import geopandas as gpd
import pandas as pd
import os

df = pd.read_csv(os.path.join(os.path.dirname(__file__), "areaperil_dict.csv"))
df.rename(columns={column:column.lower() for column in df.columns}, inplace=True)

# create the GeoDataFrame and its geometry
gdf_peril_area = gpd.GeoDataFrame(df)

gdf_peril_area["area_peril_geometry"] = gdf_peril_area.apply(lambda row: Point(row["longitude"], row["latitude"]),
                                        axis=1,
                                        result_type='reduce')
gdf_peril_area = gdf_peril_area.set_geometry('area_peril_geometry')

# store to parquet format
gdf_peril_area.to_parquet(os.path.join(os.path.dirname(__file__), "areaperil_dict.parquet"))