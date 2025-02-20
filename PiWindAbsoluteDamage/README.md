<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# Oasis PiWind Absolute Damage

The absolute damage option allows model providers to include absolute damage amounts rather than damage factors in the damage bin dictionary. If the damage factors are less than or equal to 1 in the damage bin dictionary, the factor will be applied as normal during the loss calculation, by applying the sampled damage factor to the TIV to give a simulated loss; but with absolute damage factors, where the factor is greater than 1, the TIV is not used in the calculation at all, but rather the absolute damage is applied as the loss.

Example 1: if the sampled damage factor is 0.6 and the TIV is 100,000, the sampled loss will be 60,000

Example 2: if the sampled damage factor is 500 and the TIV is 100,000, the sampled loss will be 500

More information on absolute damage can be found [here](https://oasislmf.github.io/sections/absolute-damage.html).