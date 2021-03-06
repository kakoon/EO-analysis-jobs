#!/usr/bin/env ipython
"""
Producer script for raft-level PTC analysis.
"""

def run_ptc_task(sensor_id):
    import lsst.eotest.sensor as sensorTest
    import siteUtils
    import eotestUtils

    file_prefix = '%s_%s' % (sensor_id, siteUtils.getRunNumber())
    flat_files = siteUtils.dependency_glob('S*/%s_flat*flat?_*.fits' % sensor_id,
                                           jobname=siteUtils.getProcessName('flat_pair_raft_acq'),
                                           description='Flat files:')
    bias_frame = siteUtils.dependency_glob('%s_sflat*median_bias.fits'
                                           % sensor_id,
                                           description='Super bias frame:')[0]
    mask_files = \
        eotestUtils.glob_mask_files(pattern='%s_*mask.fits' % sensor_id)
    gains = eotestUtils.getSensorGains(jobname='fe55_raft_analysis',
                                       sensor_id=sensor_id)

    task = sensorTest.PtcTask()
    task.run(sensor_id, flat_files, mask_files, gains, bias_frame=bias_frame)

    results_file = '%s_eotest_results.fits' % sensor_id
    plots = sensorTest.EOTestPlots(sensor_id, results_file=results_file)
    siteUtils.make_png_file(plots.ptcs,
                            '%s_ptcs.png' % file_prefix,
                            ptc_file='%s_ptc.fits' % sensor_id)

if __name__ == '__main__':
    from multiprocessor_execution import sensor_analyses

    processes = 9                # Reserve 1 process per CCD.
    sensor_analyses(run_ptc_task, processes=processes)
