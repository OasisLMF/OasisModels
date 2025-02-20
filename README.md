# Oasis Models
Example Oasis models for use in demonstrations and testing


## Deterministic Model
This is a single event model which allows users to apply deterministic losses to a portfolio, defining the damage factors in the OED location file. It is similar to the `exposure` feature in the oasislmf package, but can be deployed as a model in it's own right to model deterministic losses which can then be passed through the Oasis financial module.

## Paris Windstorm
This is very small, single peril model used for demonstration of how to build a simple model in Oasis.

## PiWind
This is the original test model in Oasis and is an example of a multi-peril model implementation representing ficticious events with wind and flood affecting the Town of Melton Mowbray in England.

## PiWind Absolute Damage
This model expands upon the PiWind model with the absolute damage option. This option allows model providers to include absolute damage amounts rather than damage factors in the damage bin dictionary. If the damage factors are less than or equal to 1 in the damage bin dictionary, the factor will be applied as normal during the loss calculation, by applying the sampled damage factor to the TIV to give a simulated loss; but with absolute damage factors, where the factor is greater than 1, the TIV is not used in the calculation at all, but rather the absolute damage is applied as the loss.

## PiWind Complex Model
This is a version of the PiWind model which uses the complex model integreation approach to generate ground up losses in a custoim module, which then sits in the workflow and replaces the standard ground up loss calculation from Oasis

## PiWind Postcode
This is a variant of the original PiWind model designed for running exposures whose locations are known at postcode level rather than by latitude and longitude. This model demonstrates the disaggregation features of Oasis.

## PiWind Post Loss Amplification
This is a version of the PiWind model with post loss amplification factors applied. Major catastrophic events can give rise to inflated and/or deflated costs depending on that specific situation. To account for this, the ground up losses produced by the GUL calculation component are multiplied by post loss amplification factors, by the component plapy.

## PiWind Pre Analysis
This model builds upon the original PiWind model with a pre-analysis adjustment hook. This step allows the user to modify input files before they are processed in the analysis. This functionality is utilised by this model by implementing an external geocoder: this checks the location data before it is analysed for any addresses that are missing OED location data. If an address is found to be incomplete, it is geocoded to fill these gaps.

## PiWind Single Peril
This is a simplified variant of the original PiWind model which has single peril (wind only) and would be a good basis for a single peril model in Oasis

## PiWind Vulnerability Adjustments
This model showcases how specific adjustments to the vulnerabilities can be introduced in `the analysis_settings.json` file. The `tests` folder contains three examples of the different ways the adjustments can be applied.
