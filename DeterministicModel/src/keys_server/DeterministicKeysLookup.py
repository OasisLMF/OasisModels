# -*- coding: utf-8 -*-

__all__ = [
  'DeterministicKeysLookup'
] 

# Python standard library imports
import json
import io
import os

# Python non-standard library imports
import pandas as pd

# Oasis utils and other Oasis imports
from oasislmf.utils.log import oasis_log
from oasislmf.utils.status import OASIS_KEYS_STATUS
from oasislmf.preparation.lookup import OasisBaseKeysLookup


class DeterministicKeysLookup(OasisBaseKeysLookup):

    @oasis_log()
    def __init__(self, 
            keys_data_directory=None, 
            supplier='OasisLMF', 
            model_name='Deterministic', 
            model_version='0.0.1',
            complex_lookup_config_fp=None,
            output_directory=None
        ):
        """
        Initialise the static data required for the lookup.
        """
        super(self.__class__, self).__init__(
            keys_data_directory,
            supplier,
            model_name,
            model_version,
            complex_lookup_config_fp,
            output_directory
        )

        # perils
        with io.open(os.path.join(self.keys_data_directory,'perils.json'),'r',encoding='utf-8') as p:
            self.perils = json.load(p)

        # area perils
        with io.open(os.path.join(self.keys_data_directory,'areaperils.json'),'r',encoding='utf-8') as ap:
            self.areaperils = json.load(ap)

    def get_perils(self,locperilscovered):
        source_peril_list = locperilscovered.replace(' ','').split(';')
        target_peril_list = []

        if len(source_peril_list) > 0:
            for sp in source_peril_list:
                target_perils = self.perils[sp]
                for tp in target_perils:
                    target_peril_list.append(tp)
        
        #remove duplicates
        return_perils = list(set(target_peril_list))

        return return_perils

    def get_areaperil(self,peril):
        ap_id = self.areaperils[peril]
        return ap_id

    @oasis_log()
    def process_locations(self, loc_df):
        """
        Process location rows - passed in as a pandas dataframe.
        """

        loc_df = loc_df.rename(columns=str.lower)

        required_columns = {
            1:"flexilocbuildingdr",
            2:"flexilocotherdr",
            3:"flexiloccontentsdr",
            4:"flexilocbidr"
            }

        #set dr = 100 where not provided
        loc_df_cols = loc_df.columns
        for col_id in required_columns:
            if required_columns[col_id] not in loc_df_cols:
                loc_df[required_columns[col_id]] = 1.0


        for index, row in loc_df.iterrows():
            loc_id = row['loc_id']
            locperilscovered = row['locperilscovered']
            lst_perils = self.get_perils(locperilscovered)
            # replaced with just WTC for simplicity
            # lst_perils = ['WTC']
            status = OASIS_KEYS_STATUS['success']['id']


            for peril in lst_perils:
                ap_id = self.get_areaperil(peril)
                for cov in range(1,5):
                    dr_col = required_columns[cov]
                    dr = float(row[dr_col])*100
                    v_id = int(dr)

                    yield {
                        "loc_id": int(loc_id),
                        "peril_id": peril,
                        "coverage_type": int(cov),
                        "area_peril_id": ap_id,
                        "vulnerability_id": v_id,
                        "message": '',
                        "status": status
                    }

