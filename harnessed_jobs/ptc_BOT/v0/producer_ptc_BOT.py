#!/usr/bin/env python
"""
Producer script for BOT PTC analysis.
"""
def ptc_jh_task(det_name):
    """JH version of single sensor execution of the PTC task."""
    import glob
    import siteUtils
    from bot_eo_analyses import make_file_prefix, glob_pattern,\
        get_amplifier_gains, bias_filename, ptc_task

    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    flat_files = siteUtils.dependency_glob(glob_pattern('ptc', det_name),
                                           acq_jobname=acq_jobname)
    if not flat_files:
        print("ptc_task: Flat pairs files not found for detector", det_name)
        return None

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)
    bias_frame = bias_filename(file_prefix)

    return ptc_task(run, det_name, flat_files, gains,
                    mask_files=mask_files, bias_frame=bias_frame)


if __name__ == '__main__':
    from bot_eo_analyses import get_analysis_types, run_jh_tasks
    if 'ptc' in get_analysis_types():
        run_jh_tasks(ptc_jh_task)
