import argparse
import json
import logging
import math
import numpy as np
import os
import pandas as pd
import struct
import sys


logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

output_stdout = sys.stdout.buffer


def parse_arguments():
    """
    Read arguments from command line and check validity.

    :return: arguments
    :dtype: namespace object
    """

    parser = argparse.ArgumentParser(description='Ground up loss generation.')
    parser.add_argument(
        '-e', '--event-batch', required=True, nargs=2, type=int,
        help='The nth batch out of m'
    )
    parser.add_argument(
        '-a', '--analysis-settings-file', required=True,
        help='The analysis settings file'
    )
    parser.add_argument(
        '-p', '--inputs-directory', required=True, help='The inputs directory'
    )
    parser.add_argument(
        '-f', '--complex-items-filename', default='complex_items.bin',
        help='The complex items file name'
    )
    parser.add_argument(
        '-i', '--loss-output-stream', required=True, default=None,
        help='Loss output stream'
    )

    args = parser.parse_args()

    # Check files and directories exist
    if not os.path.exists(args.analysis_settings_file):
        raise Exception('Analysis settings file does not exist.')
    inputs_dir = args.inputs_directory
    if not os.path.exists(inputs_dir):
        raise Exception('Inputs directory does not exist.')
    complex_items_fp = os.path.join(inputs_dir, args.complex_items_filename)
    if not os.path.exists(complex_items_fp):
        raise Exception('Complex items file does not exist.')
    # Check event batch validity
    (event_batch, max_event_batch) = args.event_batch
    if event_batch > max_event_batch:
        raise Exception('Invalid event batch.')

    return args


def check_bin_file_exists_and_read_it(file_desc, input_fp, conversion_tool):
    """
    Check model data or complex items binary file exists, convert to csv using
    ktools executables and return file contents as dataframe

    :param file_desc: brief description of file to be opened
    :dtype file_desc: str

    :param input_fp: file path to binary file
    :dtype input_fp: str

    :param conversion_tool: ktools binary to csv conversion tool executable
    :dtype: str

    :return: data from binary file
    :dtype: pandas.DataFrame
    """

    if not os.path.exists(input_fp):
        raise Exception(
            f'{file_desc} file {os.path.abspath(input_fp)} does not exist.'
        )
    with os.popen(f'{conversion_tool} < {input_fp}') as p:
        input_df = pd.read_csv(p)
    input_df.columns = input_df.columns.str.replace(' ', '')
    input_df.columns = input_df.columns.str.replace('"', '')

    return input_df


def check_footprint_files_exist_and_read_them(static_dir):
    """
    Check footprint.bin and footprint.idx files exist, convert to csv using
    footprinttobin ktools executable and return file contents as dataframe

    :param static_dir: static directory
    :dtype static_dir: str

    :return: data from binary files
    :dtype: pandas.DataFrame
    """

    footprint_fp = {
        'bin': os.path.join(static_dir, 'footprint.bin'),
        'idx': os.path.join(static_dir, 'footprint.idx')
    }
    for k, v in footprint_fp.items():
        if not os.path.exists(v):
            raise Exception(
                f'Footprint {k} file {os.path.abspath(v)} does not exist.'
            )
    with os.popen(f"footprinttocsv -b {footprint_fp['bin']} -x {footprint_fp['idx']}") as p:
        df_foot = pd.read_csv(p)
    df_foot.columns = df_foot.columns.str.replace(' ', '')

    return df_foot


def get_event_ids(inputs_dir, event_batch, max_event_batch):
    """
    Get event IDs from events file. Randomises and splits event IDs over
    multiple batches.

    :param inputs_dir: inputs directory
    :dtype inputs_dir: str

    :param event_batch: batch number
    :dtype event_batch: int

    :param max_event_batch: maximum number of batches
    :dtype max_event_batch: int

    :return: event IDs
    :dtype: numpy.ndarray
    """

    # Check events file exists and open it
    events_file = 'events.bin'
    events_fp = os.path.join(inputs_dir, events_file);
    if not os.path.exists(events_fp):
        raise Exception('Events file does not exist.')
    with os.popen(f'evetocsv < {events_fp}') as p:
        events_pd = pd.read_csv(p)

    # Randomise event IDs and sort into batches
    np.random.seed(1234)   # Use same random seed for all batches
    events_pd['event_id'] = np.random.choice(
        events_pd['event_id'], events_pd.size, replace=False
    )
    chunksize = math.ceil(events_pd.size / max_event_batch)
    start_position = chunksize * (event_batch - 1)
    end_position = chunksize * event_batch
    if end_position > events_pd.size:
        end_position = events_pd.size

    return events_pd['event_id'].to_numpy()[start_position:end_position]


def get_model(event_ids, inputs_dir, static_dir):
    """
    Get Cummulative Distribution Functions (CDFs) from event ids, merging data
    from model data files. Also returns damage bin dictionary and item
    dataframes.

    :param event_ids: event IDs
    :dtype event_ids: numpy.ndarray

    :param inputs_dir: inputs directory
    :dtype inputs_dir: str

    :param static_dir: static directory
    :dtype static_dir: str

    :return df_model: summary of model data required to calculate ground up losses
    :dtype df_model: pandas.DataFrames

    :return df_items: contents of items file
    :dtype df_items: pandas.DataFrame

    :return df_damage_bin_dict: contents of damage bin dictionary file
    :dtype df_damage_bin_dict: pandas.DataFrame
    """

    df_model = pd.DataFrame({'event_id': event_ids})

    df_model['order'] = df_model.index   # Preserve initial order

    # Merge areaperil_id from footprint file
    df_foot = check_footprint_files_exist_and_read_them(static_dir)
    # No intensity uncertainty so probabilities are all 1 and not needed
    df_foot.drop('probability', axis=1, inplace=True)
    df_foot.rename(columns={'areaperil_id': 'area_peril_id'}, inplace=True)
    df_model = pd.merge(df_model, df_foot, how='inner', on='event_id')
    del df_foot   # Unrequired: delete to free memory

    # Merge vulnerability_id from model data in complex items file
    df_items = check_bin_file_exists_and_read_it(
        'Complex items', os.path.join(inputs_dir, 'complex_items.bin'),
        'complex_itemtocsv'
    )
    model_data_fields = ['area_peril_id', 'vulnerability_id']
    for field in model_data_fields:
        df_items[field] = [
            d.get(field) for d in df_items.model_data.apply(eval)
        ]
    # Drop model_data column to free memory
    df_items.drop('model_data', axis=1, inplace=True)
    df_model = pd.merge(
        df_model, df_items[model_data_fields], how='inner', on='area_peril_id'
    ).drop_duplicates()

    # Merge damage_bin_index from vulnerability file
    df_vul = check_bin_file_exists_and_read_it(
        'Vulnerability', os.path.join(static_dir, 'vulnerability.bin'),
        'vulnerabilitytocsv'
    )
    # Calculate cummulative probability
    df_vul['cum_prob'] = df_vul.groupby(
        ['vulnerability_id', 'intensity_bin_id']
    ).cumsum()['probability']
    df_model = pd.merge(
        df_model, df_vul, how='inner',
        on=['vulnerability_id', 'intensity_bin_id']
    )
    # Drop unrequired columns and dataframe to free memory
    df_model.drop(['intensity_bin_id', 'probability'], axis=1, inplace=True)
    del df_vul

    # Merge interpolation from damage bin dict file
    df_damage_bin_dict = check_bin_file_exists_and_read_it(
        'Damage bin dictionary',
        os.path.join(static_dir, 'damage_bin_dict.bin'), 'damagebintocsv'
    )
    # Drop unrequired column to free memory
    #df_damage_bin_dict.drop('interval_type', axis=1, inplace=True)
    df_model = pd.merge(
        df_model, df_damage_bin_dict[['bin_index', 'interpolation']],
        how='inner', left_on='damage_bin_id', right_on='bin_index'
    )
    # Drop unrequired column to free memory
    df_model.drop('bin_index', axis=1, inplace=True)
    # Restore initial order and drop unrequired order column
    df_model.sort_values(
        by=['order', 'area_peril_id', 'vulnerability_id', 'damage_bin_id'],
        ascending=True, inplace=True
    )
    df_model.drop('order', axis=1, inplace=True)

    # Rename columns and reset index
    df_model.columns = [
        'event_id', 'areaperil_id', 'vulnerability_id', 'bin_index', 'prob_to',
        'bin_mean'
    ]
    df_model.reset_index(drop=True, inplace=True)

    return df_model, df_items, df_damage_bin_dict


def get_output_loss(loss_output_stream):
    """
    Set item output stream according to command line arguments.

    :param loss_output_stream: command line argument for loss output stream
    :dtype loss_output_stream: str

    :return: item output stream
    :dtype: stdout or file object
    """

    if loss_output_stream == '-':
        output_loss = output_stdout
    else:
        output_loss = open(loss_output_stream, 'wb')

    return output_loss


def random_number_generation(event_id, group_id, number_of_samples):
    """
    Assign 32-bit number as seed to Mersenne Twister random number generator
    and return list of random number of length equal to number of samples. Set
    up for independance between groups. Samples from a uniform distribution.

    :param event_id: event ID
    :dtype event_id: int

    :param group_id: group ID
    :dtype group_id: int

    :param number_of_samples: number of samples
    :dtype number_of_samples: int

    :return: array of random numbers sampled from uniform distribution
    :dtype: numpy.ndarray
    """

    # Calculate and assign 32-bit number as seed to Mersenne Twister random
    # number generator
    rng_seed = (group_id * 1543270363) % 2147483648
    rng_seed += (event_id * 1943272559) % 2147483648
    rng_seed %= 2147483648
    rng = np.random.Generator(np.random.MT19937(seed=rng_seed))

    return rng.uniform(size=number_of_samples)


def calculate_guls(row):
    """
    Calculate Ground Up Losses (GULs) for each sample. In this example, all bin
    means lie in the centre of their bins, and therefore the case when this is
    not true has not been included. This simplifies the function.

    :param row: sample parameters
    :dtype row: pandas Series

    :return: Ground Up Loss (GUL) value for sample
    :dtype: float
    """

    if row['bin_from'] == row['bin_to']:
        return row['bin_to'] * row['tiv']
    else:
        return (
            row['bin_from'] + (
                (row['rand'] - row['prob_from']) / (row['bin_height'])
            ) * (row['bin_width'])
        ) * row['tiv']


def gul_calc(
    number_of_samples, df_model, df_items, df_damage_bin_dict, static_dir
):
    """
    Build dataframe to calculate Group Up Losses (GULs) for all samples.

    :param number_of_samples: number of samples
    :dtype number_of_samples: int

    :param df_model: summary of model data required to calculate ground up losses
    :dtype df_model: pandas.DataFrames

    :param df_items: contents of items file
    :dtype df_items: pandas.DataFrame

    :param df_damage_bin_dict: contents of damage bin dictionary file
    :dtype df_damage_bin_dict: pandas.DataFrame

    :param static_dir: static directory
    :dtype static_dir: str

    :return: Group Up Losses for all samples
    :dtype: pandas.DataFrame
    """

    # Preserve order by shuffled event_id
    df_model['order'] = pd.factorize(df_model['event_id'])[0]

    # Merge items dataframe and restore initial order
    df_items.rename(columns={'area_peril_id': 'areaperil_id'}, inplace=True)
    df_model = pd.merge(
        df_model, df_items, how='inner', on=['areaperil_id', 'vulnerability_id']
    )
    # Drop unrequired columns to free memory
    df_model.drop(['areaperil_id', 'vulnerability_id'], axis=1, inplace=True)

    # Merge TIVs from coverages file
    df_coverages = check_bin_file_exists_and_read_it(
        'Coverages', os.path.join(static_dir, 'coverages.bin'), 'coveragetocsv'
    )
    df_model = pd.merge(df_model, df_coverages, how='inner', on='coverage_id')
    df_model.sort_values(
            by=['order', 'item_id', 'bin_index'], ascending=True, inplace=True
    )

    # First step towards calculating mean and standard deviation for each
    # (event_id, item_id) pair
    df_model['prob_from'] = df_model.groupby(
        ['order', 'item_id']
    )['prob_to'].shift(1).fillna(0.0)
    df_model['bin_height'] = df_model.apply(
        lambda x: x.prob_to - x.prob_from, axis=1
    )
    df_model['mean_1'] = df_model['bin_height'] * df_model['bin_mean'] * df_model['tiv']
    df_model['std_1'] = df_model['mean_1'] * df_model['bin_mean'] * df_model['tiv']

    # Construct GUL samples dataframe
    df_gul = df_model[
        ['event_id', 'order', 'item_id', 'coverage_id', 'group_id', 'tiv']
    ].drop_duplicates()
    sidx_ls = [-3, -2, -1] + [i+1 for i in range(number_of_samples)]
    number_of_gul_combinations = len(df_gul)
    df_gul = pd.DataFrame({
        col: np.repeat(
            df_gul[col].values, len(sidx_ls)
        ) for col in df_gul.columns
    })
    df_gul['sidx'] = sidx_ls * number_of_gul_combinations
    df_gul['loss'] = 0.0   # Initialise losses for all sample indexes (sidx)
    # Mean sidx = -1
    df_gul.loc[df_gul['sidx'] == -1, 'loss'] = df_model.groupby(
        ['event_id', 'item_id']
    ).sum()['mean_1'].to_numpy()
    # Standard deviation sidx = -2
    df_gul.loc[df_gul['sidx'] == -2, 'loss'] = np.sqrt(
        df_model.groupby(
            ['event_id', 'item_id']
        ).sum()['std_1'].to_numpy() - df_gul.loc[df_gul['sidx'] == -1, 'loss'] ** 2
    ).fillna(0.0).to_numpy()
    # Drop unrequired columns from df_model to free memory
    df_model.drop(
        ['order', 'coverage_id', 'group_id', 'tiv', 'mean_1', 'std_1'], axis=1,
        inplace=True
    )

    # Random numbers for all samples (i.e. sidx > 0)
    df_gul['rand'] = 0.0
    for idx, row in df_gul[
        ['event_id', 'item_id', 'group_id']
    ].drop_duplicates().iterrows():
        eve_id = row['event_id']
        it_id = row['item_id']
        gr_id = row['group_id']
        df_gul.loc[
            (df_gul['event_id'] == eve_id) & (df_gul['item_id'] == it_id) & (df_gul['group_id'] == gr_id) & (df_gul['sidx'] > 0),
            'rand'
        ] = random_number_generation(eve_id, gr_id, number_of_samples)

    # Get location on CDF
    df_gul = pd.merge(df_gul, df_model, how='left', on=['event_id', 'item_id'])
    del df_model   # Unrequired: delete to free memory
    df_gul = df_gul[
        (df_gul['rand'] < df_gul['prob_to']) & (df_gul['rand'] >= df_gul['prob_from'])
    ]
    df_gul = pd.merge(
        df_gul,
        df_damage_bin_dict[['bin_index', 'bin_from', 'bin_to']],
        how='inner', on='bin_index'
    )
    del df_damage_bin_dict   # Unrequired: delete to free memory
    df_gul['bin_width'] = df_gul['bin_to'] - df_gul['bin_from']
    df_gul.sort_values(
        by=['order', 'item_id', 'sidx'], ascending=True, inplace=True
    )

    # Calculate GULs
    df_gul.loc[df_gul['sidx'] > 0, 'loss'] = df_gul[df_gul['sidx'] > 0].apply(
        calculate_guls, axis=1
    )

    # Calculate tiv_idx sidx = -3
    df_items_per_coverage = df_gul[
        ['event_id', 'item_id', 'coverage_id']
    ].drop_duplicates().groupby(['event_id', 'coverage_id']).count()
    df_items_per_coverage.rename(
        columns={'item_id': 'item_count'}, inplace=True
    )
    df_items_per_coverage.reset_index(inplace=True)
    df_gul = pd.merge(
        df_gul, df_items_per_coverage, how='inner',
        on=['event_id', 'coverage_id']
    )
    df_gul.loc[df_gul['sidx'] == -3, 'loss'] = df_gul['tiv'] / df_gul['item_count']

    # Implement GUL alloc rule 1
    # If total loss exceeds TIV, split TIV in same proportions as losses
    df_gul['total_loss'] = df_gul.groupby(
        ['event_id', 'coverage_id', 'sidx']
    )['loss'].transform('sum')
    df_gul.loc[
        df_gul['total_loss'] > df_gul['tiv'], ['loss']
    ] = df_gul['tiv'] * df_gul['loss'] / df_gul['total_loss']

    # Drop all but required columns
    gul_req_cols = ['event_id', 'item_id', 'sidx', 'loss']
    df_gul.drop(
        [col for col in df_gul.columns if col not in gul_req_cols], axis=1,
        inplace=True
    )

    return df_gul


def write_loss_stream(loss_output_stream, number_of_samples, df_gul):
    """
    Write loss stream to binary file in format expected by ktools exectuable
    summarycalc.

    :param loss_output_stream: loss output stream
    :dtype loss_output_stream: stdpout or file object

    :param number_of_samples: number of samples
    :dtype number_of_samples: int

    :param df_gul: Ground Up Losses (GULs) for all samples
    :dtype df_gul: pandas.DataFrame
    """

    # Handle loss output stream
    output_loss = get_output_loss(loss_output_stream)

    # Write loss output stream header
    loss_stream_id = (2 << 24) | 1
    output_loss.write(struct.pack('i', loss_stream_id))
    output_loss.write(struct.pack('i', number_of_samples))

    for event_id, item_id in df_gul[['event_id', 'item_id']].drop_duplicates().to_numpy():
        output_loss.write(struct.pack('i', event_id))
        output_loss.write(struct.pack('i', item_id))
        for row in df_gul[(df_gul['event_id'] == event_id) & (df_gul['item_id'] == item_id)].itertuples(index=False):
            output_loss.write(struct.pack('i', row[2]))   # sidx
            output_loss.write(struct.pack('f', row[3]))   # loss
        output_loss.write(struct.pack('i', 0))
        output_loss.write(struct.pack('f', 0.0))


def main():
    """
    Main function runs equivalent of eve | getmodel | gulcalc ktools stream.
    """

    # Parse arguments from command line
    args = parse_arguments()
    (event_batch, max_event_batch) = args.event_batch
    inputs_dir = args.inputs_directory

    # ktools eve equivalent
    event_ids = get_event_ids(inputs_dir, event_batch, max_event_batch)

    # Some model data files are in static directory
    parent_dir = os.path.dirname(inputs_dir)
    static_dir = os.path.join(parent_dir, 'static')

    # ktools getmodel equivalent
    df_model, df_items, df_damage_bin_dict = get_model(
        event_ids, inputs_dir, static_dir
    )

    # Read settings from analysis settings JSON
    analysis_settings = json.load(open(args.analysis_settings_file))
    try:
        number_of_samples = analysis_settings['analysis_settings']['number_of_samples']
    except KeyError:
        number_of_samples = analysis_settings['number_of_samples']

    # ktools gulcalc equivalent
    df_gul = gul_calc(
        number_of_samples, df_model, df_items, df_damage_bin_dict,
        static_dir
    )

    # Write loss stream to stdout or file
    write_loss_stream(args.loss_output_stream, number_of_samples, df_gul)


if __name__ == "__main__":
    main()
