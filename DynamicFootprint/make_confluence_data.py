"""Add the confluence example to the model data, and generate its test portfolio (tests/test_2).

A confluence is an areaperil carrying hazard under several sections, which an event can drive at
the same time (a property reachable by two rivers). Three overlapping sections, 3001-3003, are laid
over 18 areaperils of the 10x10 grid, columns 0, 1 and 9 of rows 2-7. Each row is one combination
of sections and each column one hazard uncertainty variant:

    row 7 | S2+S3     |              variant by column:
    row 6 | S1+S2+S3  |                col 0  none   - one realisation per return period
    row 5 | S1+S3     |                col 1  equal  - three realisations everywhere
    row 4 | S2        |                col 9  mixed  - the count differs between sections AND
    row 3 | S1+S2     |                               between the brackets of one section
    row 2 | S1        |
          | cols 0 1 9 |

Those cells are clear of tests/test_1's locations and of section 2143's polygon, whose edges run
along the grid's two diagonals: a point on them (col == row, or col + row == 9) can fall in or out
of 2143 on the seventh decimal of its coordinates. A section is the union of the boxes of its cells.

The lookup gives a location one row per section it falls in; the join_sections step (type
join_rows) after the section rtree folds them into one keys value ('3001;3002').

The hazard case of the model has no probability column, so realisations are written as repeated
rows: rows are weighted equally, and .25/.5/.25 is three values repeated 1, 2 and 1 times.
Base intensities differ per section and cross over between return periods, so the largest section
is not the same at every return period; all of them stay within intensity bins 1-29, which the
model's vulnerability covers.

The example adds rows for its sections to events 1-8 and leaves everything else in place: the
partitions of the other sections, their events, and section 2143's polygon. Running it again
replaces what it added.

Run from this directory: python make_confluence_data.py
"""
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
KEYS_DATA = HERE / 'keys_data'
MODEL_DATA = HERE / 'model_data'
TEST_2 = HERE / 'tests' / 'test_2'

SECTIONS = (3001, 3002, 3003)
S1, S2, S3 = SECTIONS

# grid row -> sections of that band
REGION_ROWS = {
    2: (S1,),
    3: (S1, S2),
    4: (S2,),
    5: (S1, S3),
    6: (S1, S2, S3),
    7: (S2, S3),
}
VARIANT_BY_COL = {0: 'none', 1: 'equal', 9: 'mixed'}
RETURN_PERIODS = [10, 50, 200]

# deterministic intensity per section at each return period
BASE_INTENSITY = {
    S1: {10: 8, 50: 14, 200: 20},
    S2: {10: 10, 50: 12, 200: 24},
    S3: {10: 6, 50: 16, 200: 19},
}

# realisations as (offset from the base intensity, number of repeated rows)
REALISATIONS = {
    1: [(0, 1)],
    2: [(-1, 1), (1, 1)],
    3: [(-2, 1), (0, 2), (2, 1)],
    5: [(-3, 1), (-1, 2), (0, 4), (1, 2), (3, 1)],
}

# realisation count per section and return period for the 'mixed' variant
MIXED_COUNTS = {
    S1: {10: 1, 50: 3, 200: 3},
    S2: {10: 2, 50: 3, 200: 5},
    S3: {10: 5, 50: 5, 200: 1},
}

# event_id -> [(section_id, rp_from, rp_to, interpolation)]
EVENTS = {
    1: [(S1, 10, 50, 0.5), (S2, 50, 200, 0.25), (S3, 10, 50, 0.75)],  # all three sections
    2: [(S1, 50, 200, 0.6), (S2, 10, 50, 0.3)],                       # S1+S2
    3: [(S3, 50, 200, 0.5)],                                          # S3 only
    4: [(S1, 10, 50, 0.2)],                                           # S1 only
    5: [(S2, 50, 200, 0.8), (S3, 10, 50, 0.4)],                       # S2+S3
    6: [(S1, 50, 200, 1.0), (S2, 50, 200, 1.0), (S3, 50, 200, 1.0)],  # exactly the 200 year
    7: [(S1, 10, 50, 0.0), (S2, 10, 50, 0.0), (S3, 10, 50, 0.0)],     # exactly the 10 year
    8: [(S1, 5, 10, 0.5), (S2, 5, 10, 0.5)],                          # below the lowest return period
}


def grid():
    """Areaperil points with their (col, row) position on the grid."""
    # the areaperil file carries no CRS; it is lon/lat
    areaperils = gpd.read_parquet(KEYS_DATA / 'areaperil_dict_point.parquet').set_crs('EPSG:4326')
    lons = np.unique(areaperils.geometry.x.round(7))
    lats = np.unique(areaperils.geometry.y.round(7))
    areaperils['col'] = np.searchsorted(lons, areaperils.geometry.x.round(7))
    areaperils['row'] = np.searchsorted(lats, areaperils.geometry.y.round(7))
    return areaperils, lons, lats


def edges(centres):
    """Cell edges half-way between grid points, one cell beyond each end."""
    step = centres[1] - centres[0]
    return np.concatenate([[centres[0] - step / 2], (centres[:-1] + centres[1:]) / 2, [centres[-1] + step / 2]])


def make_sections(lons, lats):
    lon_edges, lat_edges = edges(lons), edges(lats)
    return gpd.GeoDataFrame([
        {'section_id': section_id,
         'geometry': unary_union([box(lon_edges[col], lat_edges[row], lon_edges[col + 1], lat_edges[row + 1])
                                  for row, sections in REGION_ROWS.items() if section_id in sections
                                  for col in VARIANT_BY_COL])}
        for section_id in SECTIONS
    ], crs='EPSG:4326')


def confluence_cells(areaperils):
    cells = areaperils[areaperils['row'].isin(REGION_ROWS) & areaperils['col'].isin(VARIANT_BY_COL)]
    return cells.sort_values(['row', 'col'])


def make_hazard_case(cells):
    rows = []
    for cell in cells.itertuples():
        variant = VARIANT_BY_COL[cell.col]
        for section_id in REGION_ROWS[cell.row]:
            for rp in RETURN_PERIODS:
                count = {'none': 1, 'equal': 3, 'mixed': MIXED_COUNTS[section_id][rp]}[variant]
                for offset, repeat in REALISATIONS[count]:
                    rows += [(section_id, cell.area_peril_id, rp, BASE_INTENSITY[section_id][rp] + offset)] * repeat
    return pd.DataFrame(rows, columns=['section_id', 'areaperil_id', 'return_period', 'intensity'])


def make_event_definition():
    rows = [(event_id, round(rp_from + interpolation * (rp_to - rp_from)), section_id, rp_from, rp_to, interpolation)
            for event_id, event_sections in EVENTS.items()
            for section_id, rp_from, rp_to, interpolation in event_sections]
    return pd.DataFrame(rows, columns=['event_id', 'rp', 'section_id', 'rp_from', 'rp_to', 'interpolation'])


def make_locations(cells):
    return pd.DataFrame([{
        'PortNumber': 1, 'AccNumber': 'A11111', 'LocNumber': i,
        'BuildingID': 1, 'CountryCode': 'GB',
        'Latitude': round(cell.geometry.y, 7), 'Longitude': round(cell.geometry.x, 7),
        'StreetAddress': f"{'+'.join(f'S{SECTIONS.index(s) + 1}' for s in REGION_ROWS[cell.row])} "
                         f"{VARIANT_BY_COL[cell.col]} col {cell.col} row {cell.row}",
        'OccupancyCode': 1050, 'ConstructionCode': 5000, 'LocPerilsCovered': 'OSF',
        'BuildingTIV': 100000, 'OtherTIV': 0, 'ContentsTIV': 0, 'BITIV': 0,
        'LocCurrency': 'GBP', 'OEDVersion': '5.0.0',
        'FirstFloorHeight': 0, 'CustomFloodSOP': 0,
    } for i, cell in enumerate(cells.itertuples(), start=1)])


def write_section_dict(sections):
    path = KEYS_DATA / 'section_dict.parquet'
    existing = gpd.read_parquet(path)
    existing = existing[~existing['section_id'].isin(SECTIONS)]
    # the existing polygon carries no CRS: it is lon/lat like the rest of the keys data
    if existing.crs is None:
        existing = existing.set_crs('EPSG:4326')
    pd.concat([existing, sections], ignore_index=True).to_parquet(path)


def write_hazard_case(hazard_case):
    dataset = MODEL_DATA / 'hazard_case.parquet'
    for section_id, rows in hazard_case.groupby('section_id'):
        partition = dataset / f'section_id={section_id}'
        shutil.rmtree(partition, ignore_errors=True)
        partition.mkdir()
        # same columns and types as the model's other partitions
        rows.drop(columns='section_id').astype('int64').to_parquet(partition / 'confluence.parquet', index=False)


def write_event_definition(event_definition):
    path = MODEL_DATA / 'event_definition.parquet'
    existing = pd.read_parquet(path)
    existing = existing[~existing['section_id'].isin(SECTIONS)]
    merged = pd.concat([existing, event_definition.astype(existing.dtypes.to_dict())], ignore_index=True)
    merged.sort_values(['event_id', 'section_id'], kind='stable').to_parquet(path, index=False)


def main():
    areaperils, lons, lats = grid()
    cells = confluence_cells(areaperils)
    write_section_dict(make_sections(lons, lats))
    write_hazard_case(make_hazard_case(cells))
    write_event_definition(make_event_definition())
    TEST_2.mkdir(parents=True, exist_ok=True)
    make_locations(cells).to_csv(TEST_2 / 'location.csv', index=False)


if __name__ == '__main__':
    main()
