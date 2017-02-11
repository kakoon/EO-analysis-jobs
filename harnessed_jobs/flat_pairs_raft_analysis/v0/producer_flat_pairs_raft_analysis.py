#!/usr/bin/env python
"""
Producer script for raft-level flat pairs analysis.
"""
from __future__ import print_function
import lsst.eotest.sensor as sensorTest
import siteUtils
import eotestUtils
import camera_components

raft_id = siteUtils.getUnitId()
raft = camera_components.Raft.create_from_etrav(raft_id)

for sensor_id in raft.sensor_names:
    flat_files = siteUtils.dependency_glob('S*/%s_flat*flat?_*.fits' % sensor_id,
                                           jobname=siteUtils.getProcessName('flat_pair_raft_acq'),
                                           description='Flat files:')
    mask_files = \
        eotestUtils.glob_mask_files(pattern='%s_*mask.fits' % sensor_id)
    gains = eotestUtils.getSensorGains(jobname='fe55_raft_analysis',
                                       sensor_id=sensor_id)

    task = sensorTest.FlatPairTask()
    task.run(sensor_id, flat_files, mask_files, gains,
             linearity_spec_range=(1e4, 9e4))

    results_file = '%s_eotest_results.fits' % sensor_id
    plots = sensorTest.EOTestPlots(sensor_id, results_file=results_file)

    detresp_file = '%s_det_response.fits' % sensor_id
    siteUtils.make_png_file(plots.linearity,
                            '%s_linearity.png' % sensor_id,
                            detresp_file=detresp_file)
    siteUtils.make_png_file(plots.linearity_resids,
                            '%s_linearity_resids.png' % sensor_id,
                            detresp_file=detresp_file)