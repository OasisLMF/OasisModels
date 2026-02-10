import itertools
import json

from oasislmf.utils import (
    coverages,
    peril,
)
from oasislmf.utils.status import (
    OASIS_KEYS_SC,
    OASIS_KEYS_FL,
    OASIS_KEYS_NM,
    OASIS_KEYS_STATUS
)
from oasislmf.preparation.lookup import OasisBaseKeysLookup

class ComplexAPIKeysLookup(OasisBaseKeysLookup):

    def __init__(self, 
            keys_data_directory=None,
            supplier=None,
            model_name=None,
            model_version=None,
            **kwargs):

        self._peril_ids = [
            peril.PERILS['earthquake']['id']
        ]

        self._coverage_types = [
            coverages.COVERAGE_TYPES['buildings']['id'],
            coverages.COVERAGE_TYPES['contents']['id']
        ]


    def process_location(self, loc, peril_id, coverage_type):

        status = OASIS_KEYS_SC

        latitude = loc['latitude']
        longitude = loc['longitude']
        occupancycode = loc['occupancycode']
        constructioncode = loc['constructioncode']
        yearbuilt = loc['yearbuilt']

        data = {
                "latitude": latitude,
                "longitude": longitude,
                "occupancycode": occupancycode,
                "constructioncode": constructioncode,
                "yearbuilt": yearbuilt
                }

        return {
                'loc_id': loc['loc_id'],
                'peril_id': peril_id,
                'coverage_type': coverage_type,
                'model_data': json.dumps(data),
                'status': status
                }

    def process_locations(self, loc_df):

        loc_df = loc_df.rename(columns=str.lower)

        locs_seq = (loc for _, loc in loc_df.iterrows())
        for loc, peril_id, coverage_type in \
                itertools.product(locs_seq, self._peril_ids, self._coverage_types):
            yield self.process_location(loc, peril_id, coverage_type)
