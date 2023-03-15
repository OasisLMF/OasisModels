from oasislmf.lookup.builtin import Lookup
import pandas as pd

class ParisWindstormKeysLookup(Lookup):

    @staticmethod
    def height_category(locations):
        locations['heightcategory'] = 'LowRise'
        locations.loc[locations['numberofstoreys'] >= 5, 'heightcategory'] = 'HighRise'
        locations.loc[locations['buildingheight'] >= 20, 'heightcategory'] = 'HighRise'
        return locations



        

       
