#!/usr/bin/env ipython
"""
Validator script for raft-level traps analysis.
"""
import os
import lcatr.schema
import lsst.eotest.sensor as sensorTest
import siteUtils
import eotestUtils
import camera_components

def persist_traps_analysis():
    """Persist the results from the traps analysis."""
    raft_id = siteUtils.getUnitId()
    raft = camera_components.Raft.create_from_etrav(raft_id)

    results = []
    for slot, sensor_id in raft.items():
        ccd_vendor = sensor_id.split('-')[0].upper()

        trap_file = '%s_traps.fits' % sensor_id
        eotestUtils.addHeaderData(trap_file, LSST_NUM=sensor_id,
                                  TESTTYPE='TRAP',
                                  DATE=eotestUtils.utc_now_isoformat(),
                                  CCD_MANU=ccd_vendor)
        results.append(siteUtils.make_fileref(trap_file, folder=slot))

        mask_file = '%s_traps_mask.fits' % sensor_id
        results.append(siteUtils.make_fileref(mask_file, folder=slot))

        results_file = '%s_eotest_results.fits' % sensor_id
        data = sensorTest.EOTestResults(results_file)
        amps = data['AMP']
        num_traps = data['NUM_TRAPS']

        for amp, ntrap in zip(amps, num_traps):
            results.append(lcatr.schema.valid(lcatr.schema.get('traps_raft'),
                                              amp=amp, num_traps=ntrap,
                                              slot=slot,
                                              sensor_id=sensor_id))
    return results

if __name__ == '__main__':
    if os.environ.get('LCATR_SKIP_TRAPS_ANALYSIS', 'False') == 'True':
        results = []
    else:
        results = persist_traps_analysis()

    results.extend(siteUtils.jobInfo())

    lcatr.schema.write_file(results)
    lcatr.schema.validate_file()
