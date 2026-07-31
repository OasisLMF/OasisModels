import argparse
import json
import logging
import math
import numpy as np
import os
import pandas as pd
import struct
import sys

from .api_hook import run_api

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
         '-i', '--file-in', help='not used', action='store', default='',
         type=str, dest='file_in', nargs='?'
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
        df_events = pd.read_csv(p)

    # Randomise event IDs and sort into batches
    np.random.seed(1234)   # Use same random seed for all batches
    df_events['event_id'] = np.random.choice(
        df_events['event_id'], df_events.size, replace=False
    )
    chunksize = math.ceil(df_events.size / max_event_batch)
    start_position = chunksize * (event_batch - 1)
    end_position = chunksize * event_batch
    if end_position > df_events.size:
        end_position = df_events.size

    return df_events['event_id'].to_numpy()[start_position:end_position]


def get_items(input_dir):
    """
    Build dataframe to return complex items file.

    :param input_dir: static directory, used for dummy file
    :dtype input_dir: str

    :return: items dataframe
    :dtype: pandas.DataFrame
    """

    items_file = 'complex_items.csv'
    items_fp = os.path.join(input_dir, items_file);
    df_items = pd.read_csv(items_fp)

    return df_items


def gul_calc(event_batch,event_ids, number_of_samples, df_items):
    """
    This is where you would run your api
    Links to dummy function for now
    """

    df_gul_calc = run_api(event_batch,event_ids, number_of_samples, df_items)

    return df_gul_calc


def write_loss_stream(number_of_samples, df_gul):
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

    # Write loss output stream header
    loss_stream_id = (2 << 24) | 1
    output_stdout.write(struct.pack('i', loss_stream_id))
    output_stdout.write(struct.pack('i', number_of_samples))

    for event_id, item_id in df_gul[['event_id', 'item_id']].drop_duplicates().to_numpy():
        output_stdout.write(struct.pack('i', event_id))
        output_stdout.write(struct.pack('i', item_id))
        for row in df_gul[(df_gul['event_id'] == event_id) & (df_gul['item_id'] == item_id)].itertuples(index=False):
            output_stdout.write(struct.pack('i', row[2]))   # sidx
            output_stdout.write(struct.pack('f', row[3]))   # loss
        output_stdout.write(struct.pack('i', 0))
        output_stdout.write(struct.pack('f', 0.0))


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

    # ktools getmodel equivalent
    df_items = get_items(inputs_dir)

    # Read settings from analysis settings JSON
    analysis_settings = json.load(open(args.analysis_settings_file))
    number_of_samples = analysis_settings['number_of_samples']

    # ktools gulcalc equivalent
    df_gul_calc = gul_calc(event_batch, event_ids, number_of_samples, df_items)


    # Write loss stream to stdout
    write_loss_stream(number_of_samples, df_gul_calc)


if __name__ == "__main__":
    main()
