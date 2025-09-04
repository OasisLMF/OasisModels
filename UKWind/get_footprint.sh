FP_URL="https://oasislmf-model-library-piwind-fulluk.s3.eu-west-1.amazonaws.com/footprint.bin.z"
IDX_URL="https://oasislmf-model-library-piwind-fulluk.s3.eu-west-1.amazonaws.com/footprint.idx.z"

wget "$FP_URL" -O model_data/footprint.bin.z
wget "$IDX_URL" -O model_data/footprint.idx.z
