import pandas as pd

static_loss = 100000

def run_api(event_batch, event_ids, number_of_samples, df_items):

    """
    dummy api run - returns static losses for inputs
    """

    if event_batch==1:
        # send item data to api to generate event data
        # assume we don't want to send the same thing many times.
        # skip for now
        pass
    

    df_gul_calc = pd.DataFrame(
        {
        'event_id': pd.Series(dtype='int'),
        'item_id': pd.Series(dtype='int'),
        'sidx': pd.Series(dtype='int'),
        'loss': pd.Series(dtype='float'),
        }
        )
    
    cols = ['event_id','item_id','sidx','loss']

    list_sidx = [*range(-5,0,1)] + [*range(1,number_of_samples+1,1)]

    for event_id in event_ids:
        for sidx in list_sidx:
            df_item_tmp = df_items[['item_id']].copy()
            df_item_tmp['event_id'] = event_id
            df_item_tmp['sidx'] = sidx
            df_item_tmp['loss'] = static_loss

            df_gul_calc = pd.concat([df_gul_calc,df_item_tmp[cols]])

    return df_gul_calc.sort_values(by=cols)