"""
This file mimics the newer format for overriding the default model runner. 

Suppliers use this module to edit the execution call when running ktools, 
For example setting up a complex model wrapper. 
"""
from oasislmf.execution.runner import run as oasislmf_run
from oasislmf.execution.runner import run_analysis as oasislmf_run_analysis_chunk


def run(analysis_settings,
        custom_gulcalc_cmd='OasisLMF_ComplexModelExample_gulcalc',
        **kwargs
        ):
    oasislmf_run(analysis_settings,
        custom_gulcalc_cmd='OasisLMF_ComplexModelExample_gulcalc',
        **kwargs
        )


def run_analysis(**params):
    oasislmf_run_analysis_chunk(**params)
