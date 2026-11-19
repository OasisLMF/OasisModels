"""Build the PiWindBlended model data from PiWind and the PiWindPostcode built environment.

Run from anywhere; paths are resolved relative to this file::

    python PiWindBlended/src/build_blended_model.py

Everything under ``keys_data/``, ``model_data/`` and the test exposures is regenerated
deterministically. Nothing is random.

What it builds
--------------
Wind keeps PiWind's 10x10 grid (areaperils 1-100). Surge is re-gridded onto a coarser, non-nested
7x7 grid over the same extent (areaperils 101-149), so that the two perils' cells do not line up
and a postcode's candidate positions are a genuine overlay of the two grids.

Each built-environment building (``PiWindPostcode/src/exposure_modification/OEDLocBuiltEnv.csv``)
is dropped into one wind cell and one surge cell. A *position* is a distinct (wind cell, surge cell)
pair that holds at least one building of a postcode, and its weight is that building count. So
the placement weights are integer counts (the count mode of the blended areaperil interface).

Two ways of using those same positions and weights are emitted, selected by lookup config:

- **blended**: one blended areaperil id per (postcode, peril), resolved per sample by the engine
  through ``model_data/blended_areaperil_id.csv``.
- **collapsed**: one postcode areaperil per (postcode, peril) whose footprint is the
  count-weighted mixture of its cells' hazard -- the aggregate-footprint method of PiWindPostcode,
  kept as the negative control.

The collapsed footprint does not renormalise over the cells present in an event. The weight of a
cell with no hazard in that event goes to intensity bin ``NO_HAZARD_BIN``, which every
vulnerability maps to zero damage. That keeps the collapsed control mean-correct, so a comparison
with the blended run isolates the dispersion and cross-peril coherence that blending changes,
rather than also carrying a renormalisation bias.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent
REPO = MODEL.parent
PIWIND = REPO / 'PiWind'
POSTCODE = REPO / 'PiWindPostcode'
KEYS = MODEL / 'keys_data'
DATA = MODEL / 'model_data'
TESTS = MODEL / 'tests'

N_WIND = 10                 # PiWind grid, kept as is
N_SURGE = 7                 # coarse surge grid; 7 does not divide 10, so the grids do not nest
WIND_ID0 = 1                # wind cell (ix, iy) -> 1 + ix + 10 iy, as in PiWind
FINE_SURGE_ID0 = 101        # PiWind surge cell (ix, iy) -> 101 + ix + 10 iy
SURGE_ID0 = 101             # coarse surge cell (jx, jy) -> 101 + jx + 7 jy
COLLAPSED_ID0 = {'WTC': 1000, 'WSS': 2000}     # + postcode index (1..524)
BLENDED_ID0 = {'WTC': 10000, 'WSS': 20000}     # + postcode index; scheme id = postcode index
NO_HAZARD_BIN = 59          # PiWind uses 1-29 (wind) and 30-58 (surge)
MAX_DAMAGE_BIN = 12

# Fallback vulnerabilities for OccupancyCode 1000. PiWindPostcode maps it to aggregate
# vulnerabilities 13-16, weighted per areaperil_id; how those weights should be keyed for a
# blended id is not defined yet, so this model uses PiWind's plain defaults instead.
UNKNOWN_OCCUPANCY_VULN = {('WTC', 1): 1, ('WTC', 3): 4, ('WSS', 1): 7, ('WSS', 3): 10}


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def tool(name):
    """Resolve an oasislmf console script next to the running interpreter, else on PATH."""
    local = Path(sys.executable).parent / name
    return local if local.exists() else name


def read_bin(kind, *args):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f'{kind}.csv'
        run(tool('bintocsv'), kind, *args, '-o', out)
        return pd.read_csv(out)


def grid_geometry():
    """Origin and cell size of PiWind's wind grid, checked against its id numbering."""
    d = pd.read_csv(PIWIND / 'keys_data' / 'areaperil_dict.csv')
    d = d[d.COVERAGE_TYPE == 1]
    lon = np.sort(d.LON1.unique())
    lat = np.sort(d.LAT1.unique())
    assert len(lon) == len(lat) == N_WIND
    geo = {'lon0': lon[0], 'lat0': lat[0], 'dlon': lon[1] - lon[0], 'dlat': lat[1] - lat[0]}
    ix = np.rint((d.LON1 - geo['lon0']) / geo['dlon']).astype(int)
    iy = np.rint((d.LAT1 - geo['lat0']) / geo['dlat']).astype(int)
    expected = np.where(d.PERIL_ID == 'WTC', WIND_ID0, FINE_SURGE_ID0) + ix + N_WIND * iy
    assert (expected == d.AREA_PERIL_ID).all(), 'PiWind areaperil numbering is not row-major'
    return geo


def cell_index(x, x0, extent, n):
    """Cell index of coordinate x on an n-cell grid; the far edge belongs to the last cell."""
    return np.clip(np.floor((x - x0) / extent * n).astype(int), 0, n - 1)


def coarse_surge_footprint(fp):
    """Re-grid PiWind surge onto N_SURGE x N_SURGE cells.

    A coarse cell takes the highest intensity bin of the fine surge cells it overlaps. PiWind
    surge is deterministic (one bin per cell and event), so the coarse footprint is too.
    """
    fine = fp[fp.areaperil_id >= FINE_SURGE_ID0].copy()
    k = fine.areaperil_id - FINE_SURGE_ID0
    fine['ix'], fine['iy'] = k % N_WIND, k // N_WIND

    # fine cell i spans [i, i+1)/N_WIND, coarse cell j spans [j, j+1)/N_SURGE; strict overlap
    def overlaps(i):
        return [j for j in range(N_SURGE) if j * N_WIND < (i + 1) * N_SURGE and i * N_SURGE < (j + 1) * N_WIND]

    rows = []
    for r in fine.itertuples(index=False):
        for jx in overlaps(r.ix):
            for jy in overlaps(r.iy):
                rows.append((r.event_id, SURGE_ID0 + jx + N_SURGE * jy, r.intensity_bin_id))
    coarse = pd.DataFrame(rows, columns=['event_id', 'areaperil_id', 'intensity_bin_id'])
    coarse = coarse.groupby(['event_id', 'areaperil_id'], as_index=False).intensity_bin_id.max()
    coarse['probability'] = 1.0
    return coarse


def positions(geo):
    """Count built-environment buildings per (postcode, wind cell, surge cell)."""
    b = pd.read_csv(POSTCODE / 'src' / 'exposure_modification' / 'OEDLocBuiltEnv.csv')
    ext_lon, ext_lat = geo['dlon'] * N_WIND, geo['dlat'] * N_WIND
    wx = cell_index(b.Longitude, geo['lon0'], ext_lon, N_WIND)
    wy = cell_index(b.Latitude, geo['lat0'], ext_lat, N_WIND)
    sx = cell_index(b.Longitude, geo['lon0'], ext_lon, N_SURGE)
    sy = cell_index(b.Latitude, geo['lat0'], ext_lat, N_SURGE)
    b = b.assign(WTC=WIND_ID0 + wx + N_WIND * wy, WSS=SURGE_ID0 + sx + N_SURGE * sy)
    pos = b.groupby(['PostalCode', 'WTC', 'WSS']).size().rename('weight').reset_index()
    postcodes = sorted(pos.PostalCode.unique())
    pos['scheme'] = pos.PostalCode.map({p: i + 1 for i, p in enumerate(postcodes)})
    pos = pos.sort_values(['scheme', 'WTC', 'WSS']).reset_index(drop=True)
    pos['placement_id'] = pos.groupby('scheme').cumcount()
    centroids = b.groupby('PostalCode')[['Latitude', 'Longitude']].mean()
    return pos, centroids


def blended_table(pos):
    out = []
    for peril in ('WTC', 'WSS'):
        out.append(pd.DataFrame({
            'blended_areaperil_id': BLENDED_ID0[peril] + pos.scheme,
            'placement_scheme_id': pos.scheme,
            'placement_id': pos.placement_id,
            'weight': pos.weight,
            'areaperil_id': pos[peril],
        }))
    return pd.concat(out, ignore_index=True)


def collapsed_footprint(pos, grid_fp):
    """Count-weighted mixture of each postcode's cells, per peril and event; see module docstring."""
    out = []
    for peril in ('WTC', 'WSS'):
        cw = pos.groupby(['scheme', peril], as_index=False).weight.sum().rename(columns={peril: 'areaperil_id'})
        total = cw.groupby('scheme').weight.sum()
        m = cw.merge(grid_fp, on='areaperil_id')
        m['w'] = m.weight * m.probability
        mix = m.groupby(['event_id', 'scheme', 'intensity_bin_id'], as_index=False).w.sum()
        present = mix.groupby(['event_id', 'scheme'], as_index=False).w.sum()
        present['w'] = present.scheme.map(total) - present.w
        missing = present[present.w > 0].assign(intensity_bin_id=NO_HAZARD_BIN)
        mix = pd.concat([mix, missing], ignore_index=True)
        mix['probability'] = mix.w / mix.scheme.map(total)
        mix['areaperil_id'] = COLLAPSED_ID0[peril] + mix.scheme
        out.append(mix[['event_id', 'areaperil_id', 'intensity_bin_id', 'probability']])
    return pd.concat(out, ignore_index=True)


def write_keys(pos):
    KEYS.mkdir(exist_ok=True)
    postcodes = pos.drop_duplicates('scheme')[['scheme', 'PostalCode']]
    for name, id0 in (('blended', BLENDED_ID0), ('collapsed', COLLAPSED_ID0)):
        rows = [pd.DataFrame({'area_peril_id': id0[p] + postcodes.scheme, 'peril_id': p,
                              'postalcode': postcodes.PostalCode}) for p in ('WTC', 'WSS')]
        pd.concat(rows).to_csv(KEYS / f'areaperil_dict_{name}.csv', index=False)

        cfg = json.loads((POSTCODE / 'keys_data' / 'lookup_config_postalcode_only.json').read_text())
        cfg['model']['model_id'] = 'PiWindBlended'
        cfg['model']['model_version'] = '0.0.1'
        cfg['step_definition']['peril']['parameters']['file_path'] = f'%%KEYS_DATA_PATH%%/areaperil_dict_{name}.csv'
        (KEYS / f'lookup_config_{name}.json').write_text(json.dumps(cfg, indent=4) + '\n')

    vd = pd.read_csv(POSTCODE / 'keys_data' / 'vulnerability_dict.csv')
    unknown = vd.OCCUPANCYCODE == 1000
    vd.loc[unknown, 'VULNERABILITY_ID'] = [UNKNOWN_OCCUPANCY_VULN[(p, c)] for p, c in
                                           zip(vd.PERIL_ID[unknown], vd.COVERAGE_TYPE[unknown])]
    vd.to_csv(KEYS / 'vulnerability_dict.csv', index=False)
    (KEYS / 'ModelVersion.csv').write_text('OasisLMF,PiWindBlended,0.0.1\n')


def write_model_data(pos, grid_fp, vuln):
    DATA.mkdir(exist_ok=True)
    for f in ('damage_bin_dict.bin', 'events_p.bin', 'occurrence_lt.bin', 'quantile.bin', 'returnperiods.bin'):
        shutil.copy(PIWIND / 'model_data' / f, DATA / f)

    blended_table(pos).to_csv(DATA / 'blended_areaperil_id.csv', index=False)

    fp = pd.concat([grid_fp, collapsed_footprint(pos, grid_fp)], ignore_index=True)
    fp = fp.sort_values(['event_id', 'areaperil_id', 'intensity_bin_id']).reset_index(drop=True)
    no_hazard = pd.DataFrame([(v, NO_HAZARD_BIN, d, 1.0 if d == 1 else 0.0)
                              for v in sorted(vuln.vulnerability_id.unique())
                              for d in range(1, MAX_DAMAGE_BIN + 1)], columns=vuln.columns)
    vuln = pd.concat([vuln, no_hazard]).sort_values(['vulnerability_id', 'intensity_bin_id', 'damage_bin_id'])

    with tempfile.TemporaryDirectory() as tmp:
        fp_csv, v_csv = Path(tmp) / 'footprint.csv', Path(tmp) / 'vulnerability.csv'
        fp.to_csv(fp_csv, index=False, float_format='%.6f')
        vuln.to_csv(v_csv, index=False)
        run(tool('csvtobin'), 'footprint', '-i', fp_csv, '-o', DATA / 'footprint.bin.z',
            '-x', DATA / 'footprint.idx.z', '-z', '-m', NO_HAZARD_BIN)
        run(tool('csvtobin'), 'vulnerability', '-i', v_csv, '-o', DATA / 'vulnerability.bin',
            '-d', MAX_DAMAGE_BIN, '-S')
    return fp


def write_test_exposure(pos, centroids, grid_fp):
    """Ten postcodes straddling the surge strip, plus two 12-building sites.

    Postcodes are chosen for the spread of their positions' surge hazard: a postcode whose cells
    all see the same surge has nothing to blend.
    """
    surge_cells = set(grid_fp.areaperil_id[grid_fp.areaperil_id >= SURGE_ID0])
    p = pos.assign(wet=pos.WSS.isin(surge_cells))
    stats = p.groupby(['scheme', 'PostalCode']).apply(
        lambda g: pd.Series({'n_pos': len(g), 'wet_share': g.weight[g.wet].sum() / g.weight.sum(),
                             'n_wind': g.WTC.nunique(), 'n_surge': g.WSS.nunique()}),
        include_groups=False).reset_index()
    mixed = stats[(stats.wet_share > 0.1) & (stats.wet_share < 0.9) & (stats.n_surge > 1) & (stats.n_wind > 1)]
    chosen = mixed.sort_values(['n_pos', 'scheme'], ascending=[False, True]).head(10).PostalCode.tolist()

    template = pd.read_csv(POSTCODE / 'tests' / 'test_3' / 'SourceLocOEDPiWind10_LE131DN.csv')
    row = template.iloc[0].to_dict()
    locs = []
    for i, pc in enumerate(chosen + chosen[:2]):
        n_bld = 1 if i < len(chosen) else 12
        locs.append({**row, 'LocNumber': i + 1, 'PostalCode': pc, 'StreetAddress': '',
                     'Latitude': round(centroids.Latitude[pc], 7), 'Longitude': round(centroids.Longitude[pc], 7),
                     'BuildingTIV': 150000 * n_bld, 'ContentsTIV': 37500 * n_bld, 'BITIV': 15000 * n_bld,
                     'NumberOfBuildings': n_bld})
    loc = pd.DataFrame(locs)
    for test in ('test_1', 'test_2'):
        (TESTS / test).mkdir(parents=True, exist_ok=True)
        loc.to_csv(TESTS / test / 'SourceLocOEDPiWindBlended.csv', index=False)
        shutil.copy(POSTCODE / 'tests' / 'test_3' / 'SourceAccOEDPiWind.csv', TESTS / test / 'SourceAccOEDPiWind.csv')
    return stats[stats.PostalCode.isin(chosen)]


def main():
    geo = grid_geometry()
    fp = read_bin('footprint', '-i', PIWIND / 'model_data' / 'footprint.bin', '-x', PIWIND / 'model_data' / 'footprint.idx')
    vuln = read_bin('vulnerability', '-i', PIWIND / 'model_data' / 'vulnerability.bin')
    grid_fp = pd.concat([fp[fp.areaperil_id < FINE_SURGE_ID0], coarse_surge_footprint(fp)], ignore_index=True)

    pos, centroids = positions(geo)
    write_keys(pos)
    full_fp = write_model_data(pos, grid_fp, vuln)
    chosen = write_test_exposure(pos, centroids, grid_fp)

    per_scheme = pos.groupby('scheme').agg(n_pos=('placement_id', 'size'), n_wind=('WTC', 'nunique'), n_surge=('WSS', 'nunique'))
    print(f'{pos.scheme.nunique()} schemes, {len(pos)} positions; per scheme:')
    print(per_scheme.describe().loc[['mean', 'max']].round(2).to_string())
    print(f'surge cells with hazard: {sorted(set(grid_fp.areaperil_id[grid_fp.areaperil_id >= SURGE_ID0]))}')
    print(f'footprint rows: {len(full_fp)}  (grid {len(grid_fp)})')
    print('test postcodes:')
    print(chosen.to_string(index=False))


if __name__ == '__main__':
    main()
