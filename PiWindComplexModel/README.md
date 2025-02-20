<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# Oasis PiWind Complex Model

This is an example model which uses the complex model wrapper package.

It's a version of the PiWind model which uses the complex model integreation approach to generate ground up losses in a custoim module, which then sits in the workflow and replaces the standard ground up loss calculation from Oasis

To install the package locally, you will need to run the command
```
pip install -e .
```
from within this directory, which will then use the `setup.py` file to install the ComplexModelWrapper package
