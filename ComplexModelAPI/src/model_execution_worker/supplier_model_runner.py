"""
This file mimics the newer format for overriding the default model runner.

Suppliers use this module to edit the execution call when running ktools,
For example setting up a complex model wrapper.

oasislmf calls into this module in two ways:
  - single run (MDK / platform v1):   run(), which sets the complex model's gulcalc
  - distributed run (platform v2):    run_analysis() once per loss chunk, then run_outputs();
    the chunk's gulcalc comes from the `model_custom_gulcalc` setting (docker/oasislmf.json)
"""
from oasislmf.execution.runner import run as oasislmf_run
from oasislmf.execution.runner import run_analysis as oasislmf_run_analysis_chunk
from oasislmf.execution.runner import run_outputs as oasislmf_run_outputs

CUSTOM_GULCALC_CMD = 'ComplexAPIModelExample_gulcalc'


def run(analysis_settings,
        custom_gulcalc_cmd=CUSTOM_GULCALC_CMD,
        **kwargs
        ):
    return oasislmf_run(analysis_settings,
                        custom_gulcalc_cmd=CUSTOM_GULCALC_CMD,
                        **kwargs
                        )


def run_analysis(**params):
    # Distributed loss chunk. The gulcalc command is already resolved into the params by
    # oasislmf from the `model_custom_gulcalc` setting (set in docker/oasislmf.json), so
    # setting custom_gulcalc_cmd here would have no effect.
    return oasislmf_run_analysis_chunk(**params)


def run_outputs(**params):
    # Combines the chunk results into the outputs, no gulcalc involved
    return oasislmf_run_outputs(**params)
