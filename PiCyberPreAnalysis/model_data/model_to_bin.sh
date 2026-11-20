#!/bin/bash


# damage bin dict
csvtobin damagebin -i damage_bin_dict.csv -o damage_bin_dict.bin

# events
csvtobin eve -i events.csv -o events.bin

# footprint
csvtobin footprint -z -m2 -n -i footprint.csv -o footprint.bin.z -x footprint.idx.z

# occurrence
csvtobin occurrence -P10 -i occurrence.csv -o occurrence.bin

# return periods
csvtobin returnperiods -i returnperiods.csv -o returnperiods.bin

# vulnerability
csvtobin vulnerability -d2 -N -i vulnerability.csv -o vulnerability.bin




