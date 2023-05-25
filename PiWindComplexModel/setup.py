from setuptools import setup
import src.complex_model_wrapper
import oasislmf.utils 

setup(
    name='OasisLMF_ComplexModelExample',
    version='1.0.0.0',
    entry_points={
        'console_scripts': [
            'OasisLMF_ComplexModelExample_gulcalc=src.complex_model_wrapper.OasisLMF_ComplexModelExample_gulcalc:main'
        ]
    }
)
