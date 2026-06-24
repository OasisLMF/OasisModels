FP_URL="https://oasislmf-model-library-piwind-fulluk.s3.eu-west-1.amazonaws.com/footprint.bin.z"
IDX_URL="https://oasislmf-model-library-piwind-fulluk.s3.eu-west-1.amazonaws.com/footprint.idx.z"
EXP_URL="https://oasislmf-model-library-piwind-fulluk.s3.eu-west-1.amazonaws.com/location_full.parquet"

wget "$FP_URL" -O model_data/footprint.bin.z
wget "$IDX_URL" -O model_data/footprint.idx.z
wget "$EXP_URL" -O tests/test_1/location_full.parquet"
