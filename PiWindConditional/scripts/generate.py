"""Generate the PiWindConditional toy model.

A minimal PiWind-style model demonstrating gulmc coverage dependency: Contents (coverage type
3) is a *dependent* of Building (coverage type 1) at the same location. The footprint has
genuine hazard uncertainty (several intensity bins per event), so the building's damage varies;
the contents' damage is then driven by the building's sampled damage bin through a conditional
(damage-transition) vulnerability. num_damage_bins (6) > num_intensity_bins (4) on purpose, to
exercise the correctly-sized conditional matrix.
"""
import os
import numpy as np

from oasislmf.pytools.converters.csvtobin.manager import csvtobin

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(HERE, 'model_data')
KD = os.path.join(HERE, 'keys_data')
META = os.path.join(HERE, 'meta_data')
T1 = os.path.join(HERE, 'tests', 'test_1')

N_INTENSITY = 4
N_DAMAGE = 6


def w(path, text):
    with open(path, 'w') as f:
        f.write(text.strip() + '\n')


# --- damage_bin_dict: 6 relative bins over [0, 1] ---------------------------------------
# bin 1 is the no-damage bin; interpolation = bin midpoint; damage_type 1 = relative
dbd = ["bin_index,bin_from,bin_to,interpolation,damage_type",
       "1,0.0,0.0,0.0,1"]
edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
for i in range(1, N_DAMAGE):
    lo, hi = edges[i - 1], edges[i]
    dbd.append(f"{i + 1},{lo},{hi},{(lo + hi) / 2},1")
w(os.path.join(MD, 'damage_bin_dict.csv'), "\n".join(dbd))

# --- footprint: 1 areaperil (id 1), 10 events, hazard uncertainty (multi intensity bin) --
# severity gradient from mild (low intensity bins) to severe (high). Each event's intensity
# probabilities sum to 1 -> the sampled intensity, and hence the building damage, is uncertain.
foot_events = [
    {1: 0.7, 2: 0.3},
    {1: 0.5, 2: 0.4, 3: 0.1},
    {1: 0.3, 2: 0.5, 3: 0.2},
    {2: 0.5, 3: 0.4, 4: 0.1},
    {2: 0.3, 3: 0.5, 4: 0.2},
    {2: 0.2, 3: 0.5, 4: 0.3},
    {3: 0.5, 4: 0.5},
    {3: 0.3, 4: 0.7},
    {2: 0.1, 3: 0.3, 4: 0.6},
    {4: 1.0},
]
fp = ["event_id,areaperil_id,intensity_bin_id,probability"]
for e, dist in enumerate(foot_events, start=1):
    for ibin, prob in dist.items():
        fp.append(f"{e},1,{ibin},{prob}")
_fp_csv = os.path.join(MD, '_footprint.csv')
w(_fp_csv, "\n".join(fp))
# the CSV footprint reader is unreliable, so convert to footprint.bin + footprint.idx
csvtobin(_fp_csv, os.path.join(MD, 'footprint.bin'), 'footprint',
         idx_file_out=os.path.join(MD, 'footprint.idx'), zip_files=False,
         max_intensity_bin_idx=N_INTENSITY, no_intensity_uncertainty=False,
         decompressed_size=0, no_validation=False)
os.remove(_fp_csv)

# --- building vulnerability (vuln 1): hazard-indexed, intensity -> damage distribution ---
bld = {
    1: {1: 0.5, 2: 0.5},              # mild intensity -> low damage
    2: {2: 0.5, 3: 0.5},
    3: {3: 0.4, 4: 0.4, 5: 0.2},
    4: {5: 0.5, 6: 0.5},              # severe intensity -> high damage
}
vln = ["vulnerability_id,intensity_bin_id,damage_bin_id,probability"]
for ibin in range(1, N_INTENSITY + 1):
    for dbin, prob in bld[ibin].items():
        vln.append(f"1,{ibin},{dbin},{prob}")
w(os.path.join(MD, 'vulnerability.csv'), "\n".join(vln))

# --- contents conditional vulnerability (vuln 100): P(contents bin | building bin) -------
# contents track the building's damage, one bin lower with some spread (contents a bit less
# vulnerable than the structure). intensity_bin_id column carries the SOURCE (building) bin.
cond = ["vulnerability_id,source_damage_bin,damage_bin,probability", "100,1,1,1.0"]
for src in range(2, N_DAMAGE + 1):
    cond.append(f"100,{src},{src - 1},0.4")
    cond.append(f"100,{src},{src},0.6")
w(os.path.join(MD, 'conditional_vulnerability.csv'), "\n".join(cond))

# --- events / occurrence / return periods ------------------------------------------------
n_events = len(foot_events)
n_periods = 20
np.arange(1, n_events + 1, dtype='i4').tofile(os.path.join(MD, 'events_p.bin'))

occ = ["event_id,period_no,occ_date_id"]
for e in range(1, n_events + 1):
    occ.append(f"{e},{2 * e},1")  # spread events across periods, one occurrence each
w(os.path.join(T1, '_occurrence.csv'), "\n".join(occ))
csvtobin(os.path.join(T1, '_occurrence.csv'), os.path.join(MD, 'occurrence_lt.bin'),
         'occurrence', no_of_periods=n_periods, no_date_alg=True)

w(os.path.join(T1, '_rp.csv'), "return_period\n20\n10\n5\n2")
csvtobin(os.path.join(T1, '_rp.csv'), os.path.join(MD, 'returnperiods.bin'), 'returnperiods')

# --- lookup config + vulnerability dict (WTC only; building->1, contents->100) -----------
w(os.path.join(KD, 'lookup_config.json'), """
{
    "model": {"supplier_id": "OasisLMF", "model_id": "PiWindConditional", "model_version": "0.0.0.1"},
    "builtin_lookup_type": "new_lookup",
    "keys_data_path": "./",
    "step_definition": {
        "peril": {"type": "rtree", "columns": ["latitude", "longitude"],
            "parameters": {"file_path": "%%KEYS_DATA_PATH%%/areaperil_dict.parquet", "file_type": "parquet",
                           "id_columns": ["area_peril_id"], "nearest_neighbor_min_distance": -1}},
        "split_loc_perils_covered": {"type": "split_loc_perils_covered", "columns": ["locperilscovered"],
            "parameters": {"model_perils_covered": ["WTC"]}},
        "create_coverage_type": {"type": "simple_pivot",
            "parameters": {"pivots": [{"new_cols": {"coverage_type": 1}}, {"new_cols": {"coverage_type": 3}}]}},
        "vulnerability": {"type": "merge", "columns": ["peril_id", "coverage_type", "occupancycode"],
            "parameters": {"file_path": "%%KEYS_DATA_PATH%%/vulnerability_dict.csv", "id_columns": ["vulnerability_id"]}}
    },
    "strategy": ["split_loc_perils_covered", "peril", "create_coverage_type", "vulnerability"]
}
""")
w(os.path.join(KD, 'vulnerability_dict.csv'),
  "PERIL_ID,COVERAGE_TYPE,OCCUPANCYCODE,VULNERABILITY_ID\nWTC,1,1000,1\nWTC,3,1000,100")

# --- model settings: declare the coverage dependency (building -> contents) --------------
w(os.path.join(META, 'model_settings.json'), """
{
    "model_settings": {
        "event_set": {"name": "Event Set", "desc": "toy", "default": "p",
            "options": [{"id": "p", "desc": "Probabilistic", "number_of_events": %d}]},
        "event_occurrence_id": {"name": "Occurrence Set", "desc": "toy", "default": "lt",
            "options": [{"id": "lt", "desc": "Long Term"}]},
        "coverage_dependency_settings": [
            {"source_coverage_type": 1, "dependent_coverage_type": 3}
        ]
    },
    "lookup_settings": {"supported_perils": [{"id": "WTC", "desc": "Tropical Cyclone"}]},
    "data_settings": {"damage_group_fields": ["PortNumber", "AccNumber", "LocNumber"]},
    "model_default_samples": 100
}
""" % n_events)

# --- exposure: two locations inside the WTC areaperil box, building + contents insured ----
loc = ["PortNumber,AccNumber,LocNumber,CountryCode,LocCurrency,Latitude,Longitude,"
       "LocPerilsCovered,BuildingTIV,ContentsTIV,OccupancyCode"]
loc.append("1,A,1,GB,GBP,52.737,-0.9146,WTC,1000000,500000,1000")
loc.append("1,A,2,GB,GBP,52.738,-0.9150,WTC,800000,400000,1000")
w(os.path.join(T1, 'SourceLocOEDPiWindConditional.csv'), "\n".join(loc))
w(os.path.join(T1, 'SourceAccOEDPiWindConditional.csv'),
  "PortNumber,AccNumber,PolNumber,AccCurrency,PolPerilsCovered,PolDed6All,PolLimit6All\n"
  "1,A,P1,GBP,WTC,0,0")

w(os.path.join(T1, 'oasislmf.json'), """
{
    "analysis_settings_json": "analysis_settings.json",
    "lookup_config_json": "../../keys_data/lookup_config.json",
    "lookup_data_dir": "../../keys_data",
    "model_data_dir": "../../model_data",
    "model_settings_json": "../../meta_data/model_settings.json",
    "oed_location_csv": "SourceLocOEDPiWindConditional.csv",
    "oed_accounts_csv": "SourceAccOEDPiWindConditional.csv"
}
""")

w(os.path.join(T1, 'analysis_settings.json'), """
{
    "analysis_tag": "conditional_toy",
    "source_tag": "MDK",
    "model_name_id": "PiWindConditional",
    "model_supplier_id": "OasisLMF",
    "gul_output": true,
    "gul_threshold": 0,
    "number_of_samples": 500,
    "model_settings": {"event_set": "p", "event_occurrence_id": "lt"},
    "gul_summaries": [
        {"id": 1, "ord_output": {"elt_sample": true,
            "ept_full_uncertainty_aep": true, "ept_full_uncertainty_oep": true, "parquet_format": false}}
    ]
}
""")

for tmp in ('_occurrence.csv', '_rp.csv'):
    os.remove(os.path.join(T1, tmp))
print("generated PiWindConditional toy model")
