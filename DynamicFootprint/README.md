<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# Oasis Dynamic Footprint Model Example

This is an example model which uses the dynamic footprint generation.

It's a version of the PiWind model which uses the dynamic footprint approach to build the footprint from the underlying hazard maps and event definitions based on the exposures presented


## Blended areaperils across basins

A location known only to its postcode can stand anywhere in the postcode, and a postcode can span
more than one *section* (river basin). This model shows how a blended areaperil works with a dynamic
footprint, and the one way it goes silently wrong.

**Model data.** `model_data/blended_areaperil_id.csv` defines two blended areaperils, each with
placements in two basins:

| Postcode | Blended id | Placements (weight → areaperil, section) |
|---|---|---|
| LE13 9BA | 99000001 | 3 → 3262281 (2143), 1 → 3495621 (2144) |
| LE13 9BB | 99000002 | 2 → 3263442 (2143), 1 → 3262281 (2143), 1 → 3496173 (2144) |

**Lookup** (`keys_data/lookup_config_blended.json`). Two `combine` steps, each trying the blended
route first and falling back to the model's own:

1. `areaperil`: the postcode's blended id from `blended_areaperil_dict.csv`, or the point rtree.
2. `sections`: the blended id's sections from `blended_section_dict.csv`, one keys row per section,
   or the section rtree.

**Every section a blended areaperil's placements lie in must be in the keys.** The dynamic footprint
loads only the sections listed in `sections.csv`, which comes from the keys. A section left out
raises no error: the placements in it simply never see hazard, so those samples lose nothing. The
lookup is responsible for this, as it is for the section of any location.

Because the event's return period is held per placement, a standard of protection is decided per
placement: location 902, protected to 1-in-25, is protected on the 2143 cell in event 1 (a 1-in-20
there) and exposed on the 2144 cell (a 1-in-50).

### Tests

| Test | Exposure | Lookup | Shows |
|---|---|---|---|
| test_1 | 10 located properties | `lookup_config.json` | the model without blending |
| test_2 | test_1 + 3 postcode-level locations (901, 902 protected to 1-in-25, 903 four buildings with a first floor at 3) | `lookup_config_blended.json` | blended locations losing in both basins |
| test_3 | as test_2 | `lookup_config_blended_missing_section.json` (section 2144 left out) | the silent loss of a missing section |
| test_4 | test_1's exposure | `lookup_config.json` | the reference for the non-blended locations |

Tests 2–4 add a per-location summary (summary set 2, by LocNumber). `tests/test_dynamic_footprint_blended.py`
in the repository root checks, from the expected results:

- the ten non-blended locations are identical in tests 2, 3 and 4, so adding blended locations and
  the blended lookup changes nothing for them;
- with both sections listed, the blended locations lose in events reaching either basin;
- with section 2144 left out, event 190 (2144 only) disappears for them, events 417 and 790 (2143
  only) are unchanged, and event 1 (both) loses the 2144 share: their analytic mean in event 1
  falls from 47,569 to 28,856, and location 902 loses nothing at all, its only exposure being on the
  missing basin. No error is raised at any point.

These need an oasislmf with blended areaperil support (gulmc only: dynamic footprints are not
supported by modelpy/gulpy).
