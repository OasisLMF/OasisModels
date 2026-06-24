<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# Oasis PiWind BI

> Note this model is a work in progress.

This is a toy UK wind model which demonstrates some features that are useful for BI.

The features implemented so far are:

- Specifying the damage type in the damage bin dictionary.

See below for further details on these changes:

## Damage type in damage bin dictionary

Model providers now have control over the damage bin types through the `damage_type` column in the damage bin dictionary. The damage types are:

- `1` : `relative`
    - The damage bins are applied as normal, where the factor defined by the bin is applied to the TIV during the loss calculation.
- `2` : `absolute`
    - The absolute damage defined by the damage bins are used in the loss calculation, the TIV is not used at all.
    - More information on absolute damage can be found [here](https://oasislmf.github.io/sections/absolute-damage.html).
- `3` : `duration`
    - The damage bins define the number of days of interruption. Therefore the loss is calculated by multiplying the sampled days by the daily loss (calculated as the `TIV / 365`).
