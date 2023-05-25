import multiprocessing
import subprocess
import os
import shutil
import logging

from oasislmf.utils.log import oasis_log
from oasislmf.execution.bash import genbash


@oasis_log()
def run(analysis_settings,
        number_of_processes=-1,
        set_alloc_rule_gul=None,
        set_alloc_rule_il=None,
        set_alloc_rule_ri=None,
        gul_legacy_stream=False,
        run_debug=False,
        custom_gulcalc_cmd=None,
        filename='run_ktools.sh',
        **kwargs
):

    if number_of_processes == -1:
        number_of_processes = multiprocessing.cpu_count()

    inferred_gulcalc_cmd = "{}_{}_gulcalc".format(
        analysis_settings.get('module_supplier_id'),
        analysis_settings.get('model_version_id'))
    if shutil.which(inferred_gulcalc_cmd):
        custom_gulcalc_cmd = inferred_gulcalc_cmd


    def custom_get_getmodel_cmd(
        number_of_samples,
        gul_threshold,
        use_random_number_file,
        coverage_output,
        item_output,
        process_id,
        max_process_id,
        gul_alloc_rule,
        stderr_guard,
        **kwargs
    ):

        cmd = "{} -e {} {} -a {} -p {}".format(
            custom_gulcalc_cmd,
            process_id,
            max_process_id,
            os.path.abspath("analysis_settings.json"),
            "input")
        if gul_legacy_stream and coverage_output != '':    
            cmd = '{} -c {}'.format(cmd, coverage_output)
        if item_output != '':
            cmd = '{} -i {}'.format(cmd, item_output)
        if stderr_guard:
            cmd = '({}) 2>> log/gul_stderror.err'.format(cmd)

        return cmd

    genbash(
        number_of_processes,
        analysis_settings,
        gul_alloc_rule=set_alloc_rule_gul,
        il_alloc_rule=set_alloc_rule_il,
        ri_alloc_rule=set_alloc_rule_ri,
        gul_legacy_stream=gul_legacy_stream,
        bash_trace=run_debug,
        filename=filename,
        _get_getmodel_cmd=custom_get_getmodel_cmd,
        **kwargs,
    )

    bash_trace = subprocess.check_output(['bash', filename])
    logging.info(bash_trace.decode('utf-8'))
