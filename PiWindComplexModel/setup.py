from setuptools import setup, find_packages

setup(
    packages=find_packages(),
    name='OasisLMF_ComplexModelExample',
    version='1.0.0.0',
    packages=find_packages(where='.'),
    package_dir={'': '.'},
    entry_points={
        'console_scripts': [
            'OasisLMF_ComplexModelExample_gulcalc=complex_model_wrapper.OasisLMF_ComplexModelExample_gulcalc:main'
        ]
    }
)
