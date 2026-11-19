"""
Checks on the DynamicFootprint blended areaperil example, read from the committed expected results.

``test_model_runs.py --check-results`` guarantees the runs still reproduce those results, so these
hold for the engine and lookup, not only for the files.

- test_3: test_1's ten locations plus three blended ones (LE13 9BA, LE13 9BB), whose placements lie
  in two basins (sections 2143 and 2144). The lookup lists both sections for them.
- test_4: the same, with a lookup that lists only section 2143 for the blended locations.
- test_5: test_1's ten locations through the model's original lookup, with the same per-location
  summaries as tests 3 and 4, as the reference for the non-blended locations.
"""
from pathlib import Path

import pandas as pd
import pytest

TESTS = Path(__file__).parent.parent / 'DynamicFootprint' / 'tests'
BLENDED_LOCATIONS = {'901', '902', '903'}
EVENT_BOTH_BASINS = 1        # reaches sections 2143 and 2144
EVENT_2144_ONLY = 190        # reaches section 2144 only
EVENTS_2143_ONLY = (417, 790)


def location_elt(test):
    """The per-location sample event loss table (summary set 2, by LocNumber) of a test's expected results."""
    output = TESTS / test / 'expected_results' / 'output'
    info = pd.read_csv(output / 'gul_S2_summary-info.csv', dtype={'LocNumber': str})
    elt = pd.read_csv(output / 'gul_S2_selt.csv')
    elt = elt.merge(info[['summary_id', 'LocNumber']], left_on='SummaryId', right_on='summary_id')
    return elt[['LocNumber', 'EventId', 'SampleId', 'Loss']].sort_values(['LocNumber', 'EventId', 'SampleId']).reset_index(drop=True)


@pytest.mark.parametrize('test', ['test_3', 'test_4'])
def test_blending_leaves_the_other_locations_unchanged(test):
    """Adding blended locations, and the blended lookup, changes nothing for the locations that are not blended."""
    with_blended = location_elt(test)
    without = location_elt('test_5')
    others = with_blended[~with_blended['LocNumber'].isin(BLENDED_LOCATIONS)].reset_index(drop=True)
    pd.testing.assert_frame_equal(others, without)


def test_blended_locations_lose_in_both_basins():
    """With both sections listed, blended locations take losses from events in either basin."""
    elt = location_elt('test_3')
    blended = elt[elt['LocNumber'].isin(BLENDED_LOCATIONS) & (elt['SampleId'] > 0)]
    by_event = blended.groupby('EventId')['Loss'].sum()
    assert by_event.get(EVENT_2144_ONLY, 0) > 0
    assert all(by_event.get(event, 0) > 0 for event in EVENTS_2143_ONLY)


def test_a_missing_section_silently_drops_that_basin():
    """A lookup that leaves out a section a blended location spans gives no error: the placements in
    that basin just never see hazard. Events reaching only the missing section vanish for the blended
    locations, events reaching only the listed one are unchanged, and an event reaching both loses
    the missing basin's share."""
    complete, missing = location_elt('test_3'), location_elt('test_4')
    blended_complete = complete[complete['LocNumber'].isin(BLENDED_LOCATIONS)].set_index(['LocNumber', 'EventId', 'SampleId'])['Loss']
    blended_missing = missing[missing['LocNumber'].isin(BLENDED_LOCATIONS)].set_index(['LocNumber', 'EventId', 'SampleId'])['Loss']

    assert (blended_complete.xs(EVENT_2144_ONLY, level='EventId') > 0).any()
    assert EVENT_2144_ONLY not in blended_missing.index.get_level_values('EventId')

    for event in EVENTS_2143_ONLY:
        pd.testing.assert_series_equal(blended_complete.xs(event, level='EventId'), blended_missing.xs(event, level='EventId'))

    both_complete = blended_complete.xs(EVENT_BOTH_BASINS, level='EventId')
    both_missing = blended_missing.xs(EVENT_BOTH_BASINS, level='EventId').reindex(both_complete.index, fill_value=0.)
    sampled = both_complete.index.get_level_values('SampleId') > 0
    assert both_missing[sampled].sum() < both_complete[sampled].sum()
