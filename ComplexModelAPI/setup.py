from setuptools import setup, find_packages
import complex_model_wrapper
import oasislmf.utils 

setup(
    name='ComplexAPIModelExample',
    version='0.0.0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'ComplexAPIModelExample_gulcalc=complex_model_wrapper.ComplexAPIModelExample_gulcalc:main'
        ]
    }
)
