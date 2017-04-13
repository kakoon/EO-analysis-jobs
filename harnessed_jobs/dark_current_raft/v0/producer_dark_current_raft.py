#!/usr/bin/env python
"""
Producer script for raft-level dark current analysis.
"""
from __future__ import absolute_import
import lsst.eotest.sensor as sensorTest
import siteUtils
import eotestUtils
from multiprocessor_execution import sensor_analyses

def run_dark_current_task(sensor_id):
    dark_files = siteUtils.dependency_glob('S*/%s_dark_dark_*.fits' % sensor_id,
                                           jobname=siteUtils.getProcessName('dark_raft_acq'),
                                           description='Dark files:')
    mask_files = \
        eotestUtils.glob_mask_files(pattern='%s_*mask.fits' % sensor_id)
    gains = eotestUtils.getSensorGains(jobname='fe55_raft_analysis',
                                       sensor_id=sensor_id)

    task = sensorTest.DarkCurrentTask()
    task.config.temp_set_point = -100.
    dark_curr_pixels, dark95s \
        = task.run(sensor_id, dark_files, mask_files, gains)

    eo_results \
        = dependency_glob('%s_eotest_results.fits' % sensor_id,
                          jobname=siteUtils.getProcessName('read_noise_raft'))
    read_noise = dict(pair for pair in zip(eo_results['AMP'],
                                           eo_results['TOTAL_NOISE']))

    siteUtils.make_png_file(sensorTest.total_noise_histogram,
                            '%s_total_noise_hists.png' % sensor_id,
                            dark_curr_pixels, read_noise, dark95s,
                            exptime=16, title=sensor_id)

if __name__ == '__main__':
    sensor_analyses(run_dark_current_task)
