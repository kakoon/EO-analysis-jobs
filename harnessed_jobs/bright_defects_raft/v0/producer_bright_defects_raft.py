#!/usr/bin/env python
"""
Producer script for raft-level bright defects analysis.
"""
from __future__ import print_function
import lsst.eotest.sensor as sensorTest
import siteUtils
import eotestUtils
import camera_components

raft_id = siteUtils.getUnitId()
raft = camera_components.Raft.create_from_etrav(raft_id)

for sensor_id in raft.sensor_names:
    dark_files = siteUtils.dependency_glob('S*/%s_dark_dark_*.fits' % sensor_id,
                                           jobname=siteUtils.getProcessName('dark_raft_acq'),
                                           description='Dark files:')
    mask_files = \
        eotestUtils.glob_mask_files(pattern='%s_*mask.fits' % sensor_id)
    gains = eotestUtils.getSensorGains(jobname='fe55_raft_analysis',
                                       sensor_id=sensor_id)

    task = sensorTest.BrightPixelsTask()
    task.config.temp_set_point = -100.
    task.run(sensor_id, dark_files, mask_files, gains)

    siteUtils.make_png_file(sensorTest.plot_flat,
                            '%s_medianed_dark.png' % sensor_id,
                            '%s_median_dark_bp.fits' % sensor_id,
                            title='%s, medianed dark for bright defects analysis' % sensor_id)