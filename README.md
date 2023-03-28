# Oasis Models
Example Oasis models for use in demonstrations and testing


## PiWind
This is the original test model in Oasis and is an example of a multi-peril model implementation representing ficticious events with wind and flood affecting the Town of Melton Mowbray in England.

## Paris Windstorm
This is very small, single peril model used for demonstration of how to build a simple model in Oasis.

## Deterministic Model
This is a single event model which allows users to apply deterministic losses to a portfolio, defining the damage factors in the OED location file. It is similar to the `exposure` feature in the oasislmf package, but can be deployed as a model in it's own right to model deterministic losses which can then be passed through the Oasis financial module.

## PiWind Postcode
This is a variant of the original PiWind model desgined for running exposures whose locations are known to PostalCode resolution rather than at a known latitude-longitude point. This model demonstrates the disaggregation features of Oasis.

