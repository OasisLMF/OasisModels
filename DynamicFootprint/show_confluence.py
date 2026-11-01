"""Print the footprint OasisLMF builds for each confluence event at tests/test_2's areaperils.

Calls FootprintParquetDynamic._build_footprint directly on the model data, so it shows the
section merge with whichever OasisLMF is installed, without a model run.

Run from this directory: python show_confluence.py [--merge max|max_independent|sum] [event_id ...]
"""
import argparse

import pandas as pd

from oasislmf.pytools.getmodel.footprint import FootprintParquetDynamic

from make_confluence_data import EVENTS, MODEL_DATA, REGION_ROWS, SECTIONS, VARIANT_BY_COL, confluence_cells, grid


def main(event_ids, section_merge):
    areaperils, _, _ = grid()
    cells = confluence_cells(areaperils)
    labels = pd.DataFrame({
        'areaperil_id': cells['area_peril_id'].to_numpy(),
        'region': ['+'.join(f'S{SECTIONS.index(s) + 1}' for s in REGION_ROWS[row]) for row in cells['row']],
        'variant': [VARIANT_BY_COL[col] for col in cells['col']],
    })
    hazard_case = pd.read_parquet(MODEL_DATA / 'hazard_case.parquet', filters=[('section_id', 'in', list(SECTIONS))])
    hazard_case['section_id'] = hazard_case['section_id'].astype('int64')
    event_definition = pd.read_parquet(MODEL_DATA / 'event_definition.parquet')
    event_definition = event_definition[event_definition['section_id'].isin(SECTIONS)]
    builder = FootprintParquetDynamic.__new__(FootprintParquetDynamic)
    builder.section_merge = section_merge

    for event_id in event_ids:
        df_event = event_definition[event_definition['event_id'] == event_id]
        footprint = builder._build_footprint(hazard_case[hazard_case['section_id'].isin(df_event['section_id'])].copy(), df_event)
        print(f"\n=== event {event_id}: sections {list(df_event['section_id'])}")
        if footprint is None:
            print('  empty')
            continue
        footprint = pd.DataFrame(footprint).merge(labels, on='areaperil_id')
        for (region, variant), rows in footprint.groupby(['region', 'variant'], sort=False):
            atoms = ', '.join(f"{r.intensity}@{r.probability:.3g}(rp{r.return_period})" for r in rows.itertuples())
            mean = (rows['intensity'] * rows['probability']).sum()
            print(f"  {region:9} {variant:6} mean {mean:6.2f} | {atoms}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--merge', default='max', help='section merge option')
    parser.add_argument('event_ids', nargs='*', type=int)
    args = parser.parse_args()
    main(args.event_ids or sorted(EVENTS), args.merge)
