#
# Generate binary files from .csv files
# See https://github.com/OasisLMF/ktools/blob/master/docs/md/DataConversionComponents.md
#

#
# Model specific parameters
#

MAX_PERIODS=1500

# extract number of intensity bins from intensity_bin_dict.csv
INTENSITY_BINS := $(shell awk -F',' '{print $$1}' intensity_bin_dict.csv | sort -n | tail -n 1)

# extract number of damage bins from damage_bin_dict.csv
DAMAGE_BINS := $(shell awk -F',' '{print $$1}' damage_bin_dict.csv | sort -n | tail -n 1)

#
# Binary file we want to generate
#
BIN_FILES= \
damage_bin_dict.bin \
footprint.bin \
footprint.idx \
vulnerability.bin \
events_p.bin \
occurrence_lt.bin \
quantile.bin \
returnperiods.bin


#
# Standard targets
#

all: $(BIN_FILES)

clean:
	rm -f $(BIN_FILES)

#
# OASIS Specifc targets
#

damage_bin_dict.bin: damage_bin_dict.csv
	csvtobin damagebin -i ./damage_bin_dict.csv -o damage_bin_dict.bin

footprint.bin: footprint.csv
	csvtobin footprint -i footprint.csv -x footprint.idx -o footprint.bin -m $(INTENSITY_BINS)

vulnerability.bin: vulnerability.csv
	csvtobin vulnerability -d $(DAMAGE_BINS) -i vulnerability.csv -o vulnerability.bin

events_p.bin: events_p.csv
	csvtobin eve -i events_p.csv -o events_p.bin

items.bin: items.csv
	csvtobin items -i items.csv -o items.bin

occurrence_lt.bin: occurrence_lt.csv intensity_bin_dict.csv
	csvtobin occurrence -P $(MAX_PERIODS) -i occurrence_lt.csv -o occurrence_lt.bin

returnperiods.bin: returnperiods.csv
	csvtobin returnperiods -i returnperiods.csv -o returnperiods.bin

periods.bin: periods.csv
	csvtobin periods -i periods.csv -o periods.bin

quantile.bin: quantile.csv
	csvtobin quantile -i quantile.csv -o quantile.bin
