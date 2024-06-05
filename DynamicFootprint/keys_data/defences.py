from oasislmf.lookup.builtin import Lookup
import pandas as pd

class UKFloodKeysLookup(Lookup):

    @staticmethod
    def defences(locations):
        locations['modeldata'] = '{"test":"test"}'
        #locations.loc[locations['numberofstoreys'] >= 5, 'heightcategory'] = 'HighRise'
        #locations.loc[locations['buildingheight'] >= 20, 'heightcategory'] = 'HighRise'
        return locations



        

       
