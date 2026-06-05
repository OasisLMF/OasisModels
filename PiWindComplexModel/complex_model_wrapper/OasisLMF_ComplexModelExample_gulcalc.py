"""
Complex model GUL wrapper — PiWind demo.

Demonstrates how a supplier model integrates with the oasislmf ktools pipeline:
  - Reads complex_items.bin (supplier-specific per-item model data)
  - Reads footprint.bin/.idx to determine per-event hazard intensity per location
  - Generates GUL samples and writes the binary stream expected by ktools downstream

The loss model is intentionally simple (intensity-weighted random fraction of TIV)
so the integration wiring is easy to follow. A production model would replace
compute_guls() with a full vulnerability CDF lookup.
"""
import argparse
import json
import logging
import msgpack
import numpy as np
import os
import struct
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ktools binary format dtypes
# ---------------------------------------------------------------------------
_ITEM_HDR_DTYPE = np.dtype([
    ('item_id', '<i4'), ('coverage_id', '<u4'), ('group_id', '<u4'), ('model_data_len', '<u4'),
])
# coverages.bin is a flat float32 array; tiv for coverage_id k is coverages[k-1]
_COVERAGES_DTYPE = np.float32
_EVENTS_DTYPE = np.dtype([('event_id', '<i4')])
_FP_IDX_DTYPE = np.dtype([('event_id', '<i4'), ('offset', '<i8'), ('size', '<i8')])
_FP_RECORD_DTYPE = np.dtype([('areaperil_id', '<u4'), ('intensity_bin_id', '<i4'), ('probability', '<f4')])
_FP_HEADER_SIZE = 8   # footprint.bin: num_intensity_bins (i4) + has_intensity_uncertainty (i4)

GUL_STREAM_ID = (2 << 24) | 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(description='Complex model GUL wrapper.')
    parser.add_argument('-e', '--event-batch', required=True, nargs=2, type=int,
                        help='Batch n of m (e.g. -e 3 12)')
    parser.add_argument('-a', '--analysis-settings-file', required=True)
    parser.add_argument('-p', '--inputs-directory', required=True)
    parser.add_argument('-f', '--complex-items-filename', default='complex_items.bin')
    parser.add_argument('-i', '--loss-output-stream', required=False, default='-',
                        nargs='?', const='-',
                        help='Output file path, or - for stdout (default); bare -i also means stdout')

    args = parser.parse_args()

    # oasislmf >= 2.x copies analysis_settings.json into the inputs directory;
    # fall back there if the given path doesn't exist.
    if not os.path.exists(args.analysis_settings_file):
        alt = os.path.join(args.inputs_directory, 'analysis_settings.json')
        if os.path.exists(alt):
            args.analysis_settings_file = alt
        else:
            raise SystemExit('Analysis settings file does not exist.')

    if not os.path.isdir(args.inputs_directory):
        raise SystemExit('Inputs directory does not exist.')

    event_batch, max_batch = args.event_batch
    if event_batch > max_batch:
        raise SystemExit('Invalid event batch.')

    return args


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def read_complex_items(inputs_dir, filename):
    """
    Parse complex_items.bin.

    Each record: item_id (i4), coverage_id (u4), group_id (u4),
                 model_data_len (u4), model_data (msgpack bytes).

    model_data is a msgpack-encoded string containing a JSON dict with at least
    'area_peril_id' and 'vulnerability_id' keys.  Only area_peril_id is used here.

    Returns four parallel int32/uint32 arrays: item_id, coverage_id, group_id, area_peril_id.
    """
    raw = np.frombuffer(open(os.path.join(inputs_dir, filename), 'rb').read(), dtype=np.uint8)
    hdr_size = _ITEM_HDR_DTYPE.itemsize

    item_ids, coverage_ids, group_ids, area_peril_ids = [], [], [], []
    cursor = 0
    while cursor + hdr_size <= len(raw):
        hdr = raw[cursor:cursor + hdr_size].view(_ITEM_HDR_DTYPE)[0]
        cursor += hdr_size

        md_bytes = raw[cursor:cursor + hdr['model_data_len']].tobytes()
        cursor += hdr['model_data_len']

        md = msgpack.unpackb(md_bytes, raw=False)
        if isinstance(md, str):
            md = json.loads(md)

        item_ids.append(hdr['item_id'])
        coverage_ids.append(hdr['coverage_id'])
        group_ids.append(hdr['group_id'])
        area_peril_ids.append(md.get('area_peril_id', 0))

    return (
        np.array(item_ids, np.int32),
        np.array(coverage_ids, np.uint32),
        np.array(group_ids, np.uint32),
        np.array(area_peril_ids, np.int32),
    )


def load_footprint(static_dir):
    """
    Memory-map footprint.bin and load the index from footprint.idx.

    footprint.bin layout:
      [num_intensity_bins (i4), has_intensity_uncertainty (i4)]   <- 8-byte header
      [areaperil_id (u4), intensity_bin_id (i4), probability (f4)] * N

    footprint.idx layout:
      [event_id (i4), offset (i8), size (i8)] * M
      where offset/size are byte positions in footprint.bin.

    Returns (fp_data, fp_idx_map, num_intensity_bins):
      fp_data       — full footprint record array
      fp_idx_map    — dict event_id -> index entry
      num_intensity_bins — number of intensity bins (for normalisation)
    """
    with open(os.path.join(static_dir, 'footprint.bin'), 'rb') as f:
        num_intensity_bins = struct.unpack('<i', f.read(4))[0]
        f.read(4)
        fp_data = np.frombuffer(f.read(), dtype=_FP_RECORD_DTYPE).copy()

    fp_idx = np.fromfile(os.path.join(static_dir, 'footprint.idx'), dtype=_FP_IDX_DTYPE)
    fp_idx_map = {int(r['event_id']): r for r in fp_idx}

    return fp_data, fp_idx_map, num_intensity_bins


def event_intensity_by_areaperil(fp_data, fp_idx_entry, num_intensity_bins):
    """
    For one event, compute probability-weighted mean intensity per areaperil_id,
    normalised to [0, 1].

    Returns (ap_ids, intensities) — parallel sorted arrays.
    """
    rec_size = _FP_RECORD_DTYPE.itemsize
    start = (int(fp_idx_entry['offset']) - _FP_HEADER_SIZE) // rec_size
    n = int(fp_idx_entry['size']) // rec_size
    records = fp_data[start:start + n]

    if records.size == 0:
        return np.empty(0, np.uint32), np.empty(0, np.float32)

    ap_ids, inv = np.unique(records['areaperil_id'], return_inverse=True)
    weighted = np.bincount(inv,
                           weights=records['intensity_bin_id'] * records['probability'],
                           minlength=len(ap_ids))
    return ap_ids, (weighted / num_intensity_bins).astype(np.float32)


def map_intensity_to_items(area_peril_ids, ap_ids, intensities):
    """
    Vectorised lookup: for each item's area_peril_id find its event intensity.

    Uses searchsorted on the sorted ap_ids array returned by np.unique.
    Items whose area_peril_id is not in ap_ids get intensity 0.
    """
    pos = np.searchsorted(ap_ids, area_peril_ids)
    pos = np.clip(pos, 0, len(ap_ids) - 1)
    found = ap_ids[pos] == area_peril_ids
    return np.where(found, intensities[pos], 0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# GUL calculation
# ---------------------------------------------------------------------------

def compute_guls(event_id, group_ids, tivs, intensity_fracs, n_samples):
    """
    Vectorised GUL calculation for all active items in one event.

    Simple loss model:
      sample = intensity_frac * U[0,1] * tiv
      mean   = intensity_frac * tiv             (sidx = -1)
      std    = tiv * sqrt(intensity_frac / 3)   (uniform distribution std)
      tiv    = tiv                              (sidx = -3, TIV index)

    All samples are capped at TIV.

    Random numbers are generated in a single vectorised call seeded by event_id
    (one stream per unique group_id). A production model would use per-group
    MT19937 seeding for full correlation control.

    Returns sample_losses (n_items × n_samples), mean_losses (n_items,),
            std_losses (n_items,).
    """
    unique_gids, inv = np.unique(group_ids, return_inverse=True)
    rand_matrix = np.random.default_rng(event_id).uniform(
        size=(len(unique_gids), n_samples)
    ).astype(np.float32)

    item_rands = rand_matrix[inv]                                           # (n_items, n_samples)
    f = intensity_fracs[:, np.newaxis]                                      # (n_items, 1)
    t = tivs[:, np.newaxis]                                                 # (n_items, 1)

    sample_losses = np.minimum(f * item_rands * t, t).astype(np.float32)   # (n_items, n_samples)
    mean_losses = (intensity_fracs * tivs).astype(np.float32)
    std_losses = (tivs * np.sqrt(np.maximum(intensity_fracs / 3.0, 0))).astype(np.float32)

    return sample_losses, mean_losses, std_losses


# ---------------------------------------------------------------------------
# Binary stream output
# ---------------------------------------------------------------------------

def write_event_to_stream(out, event_id, item_ids, tivs, mean_losses, std_losses, sample_losses):
    """
    Write one event's GUL records to the output stream.

    Per-item binary layout (all fields 4 bytes, little-endian):
      event_id (i4)  item_id (i4)
      sidx=-3 (i4)   tiv (f4)
      sidx=-2 (i4)   std (f4)
      sidx=-1 (i4)   mean (f4)
      sidx=1  (i4)   sample_1 (f4)
      ...
      sidx=n  (i4)   sample_n (f4)
      0       (i4)   0.0 (f4)          <- terminator
    """
    n_items = len(item_ids)
    n_samples = sample_losses.shape[1]
    n_pairs = 3 + n_samples + 1     # sidx=-3,-2,-1, 1..n, terminator

    sidxs = np.array([-3, -2, -1] + list(range(1, n_samples + 1)) + [0], dtype='<i4')

    # losses_matrix: (n_items, n_pairs) — tiv, std, mean, samples..., 0.0
    losses_matrix = np.hstack([
        tivs[:, np.newaxis],
        std_losses[:, np.newaxis],
        mean_losses[:, np.newaxis],
        sample_losses,
        np.zeros((n_items, 1), dtype=np.float32),
    ]).astype('<f4')

    # Interleave sidx (i4) and loss (f4) columns as raw u4 bytes
    interleaved = np.empty((n_items, 2 * n_pairs), dtype='<u4')
    interleaved[:, 0::2] = sidxs.view('<u4')
    interleaved[:, 1::2] = losses_matrix.view('<u4')

    # Prepend event_id and item_id header columns
    headers = np.empty((n_items, 2), dtype='<i4')
    headers[:, 0] = event_id
    headers[:, 1] = item_ids

    full = np.hstack([headers.view('<u4'), interleaved])
    out.write(full.tobytes())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_arguments()
    event_batch, max_event_batch = args.event_batch
    inputs_dir = args.inputs_directory
    static_dir = os.path.join(os.path.dirname(os.path.abspath(inputs_dir)), 'static')

    with open(args.analysis_settings_file) as f:
        settings = json.load(f)
    try:
        n_samples = settings['analysis_settings']['number_of_samples']
    except KeyError:
        n_samples = settings['number_of_samples']

    log.info('Loading complex items...')
    item_ids, coverage_ids, group_ids, area_peril_ids = read_complex_items(
        inputs_dir, args.complex_items_filename
    )

    coverages = np.fromfile(os.path.join(static_dir, 'coverages.bin'), dtype=_COVERAGES_DTYPE)
    item_tivs = coverages[coverage_ids - 1]   # coverage_ids are 1-based

    # Batch selection: shuffle all events with fixed seed then slice, matching
    # the behaviour of the original implementation for reproducibility.
    all_events = np.fromfile(os.path.join(inputs_dir, 'events.bin'), dtype=_EVENTS_DTYPE)['event_id']
    np.random.seed(1234)
    shuffled = np.random.choice(all_events, len(all_events), replace=False)
    chunk = int(np.ceil(len(shuffled) / max_event_batch))
    batch = shuffled[(event_batch - 1) * chunk: min(event_batch * chunk, len(shuffled))]

    log.info('Loading footprint...')
    fp_data, fp_idx_map, num_intensity_bins = load_footprint(static_dir)

    out = sys.stdout.buffer if args.loss_output_stream == '-' else open(args.loss_output_stream, 'wb')
    out.write(struct.pack('<ii', GUL_STREAM_ID, n_samples))

    log.info(f'Processing batch {event_batch}/{max_event_batch} ({len(batch)} events)...')
    for event_id in batch:
        event_id = int(event_id)
        if event_id not in fp_idx_map:
            continue

        ap_ids, intensities = event_intensity_by_areaperil(fp_data, fp_idx_map[event_id], num_intensity_bins)
        item_intensities = map_intensity_to_items(area_peril_ids, ap_ids, intensities)

        active = item_intensities > 0
        if not np.any(active):
            continue

        sample_losses, mean_losses, std_losses = compute_guls(
            event_id,
            group_ids[active], item_tivs[active], item_intensities[active],
            n_samples,
        )

        write_event_to_stream(
            out, event_id,
            item_ids[active], item_tivs[active],
            mean_losses, std_losses, sample_losses,
        )

    if args.loss_output_stream != '-':
        out.close()


if __name__ == '__main__':
    main()
