#!/usr/bin/env ipython
"""
Validator script for raft-level Fe55 analysis.
"""
from __future__ import print_function
import os
import glob
import numpy as np
import lcatr.schema
import siteUtils
import eotestUtils
import lsst.eotest.sensor as sensorTest
import lsst.eotest.image_utils as imutils
import camera_components


def persist_fe55_gains():
    """Persist only the Fe55 gains from the results file."""
    raft_id = siteUtils.getUnitId()
    raft = camera_components.Raft.create_from_etrav(raft_id)
    results = []
    for slot, sensor_id in raft.items():
        # Save eotest results file with nominal gains.
        ccd_vendor = sensor_id.split('-')[0].upper()
        results_file = '%s_eotest_results.fits' % sensor_id
        eotestUtils.addHeaderData(results_file, LSST_NUM=sensor_id,
                                  TESTTYPE='FE55',
                                  DATE=eotestUtils.utc_now_isoformat(),
                                  CCD_MANU=ccd_vendor)
        results.append(lcatr.schema.fileref.make(results_file))

        # Persist nominal values to eT results database.
        amps = imutils.allAmps()
        gain_data = np.ones(len(amps))
        gain_errors = np.zeros(len(amps))
        sigmas = np.zeros(len(amps))
        for amp, gain_value, gain_error, sigma in zip(amps, gain_data,
                                                      gain_errors, sigmas):
            if not np.isfinite(gain_error):
                gain_error = -1
            results.append(lcatr.schema.valid(
                    lcatr.schema.get('fe55_raft_analysis'),
                    amp=amp, gain=gain_value,
                    gain_error=gain_error,
                    psf_sigma=sigma,
                    slot=slot,
                    sensor_id=sensor_id))

    return results


def persist_fe55_analysis_results():
    """Persist the results from the full analysis."""
    raft_id = siteUtils.getUnitId()
    raft = camera_components.Raft.create_from_etrav(raft_id)

    results = []
    for slot, sensor_id in raft.items():
        ccd_vendor = sensor_id.split('-')[0].upper()
        # The output files from producer script.
        gain_file = '%(sensor_id)s_eotest_results.fits' % locals()
        psf_results = glob.glob('%(sensor_id)s_psf_results*.fits' % locals())[0]
        rolloff_mask = '%(sensor_id)s_rolloff_defects_mask.fits' % locals()

        output_files = gain_file, psf_results, rolloff_mask

        # Add/update the metadata to the primary HDU of these files.
        for fitsfile in output_files:
            eotestUtils.addHeaderData(fitsfile, LSST_NUM=sensor_id,
                                      TESTTYPE='FE55',
                                      DATE=eotestUtils.utc_now_isoformat(),
                                      CCD_MANU=ccd_vendor)

        #
        # Persist the median bias FITS file.
        #
        bias_median_file = glob.glob(f'{sensor_id}_*_median_bias.fits')[0]
        results.append(siteUtils.make_fileref(bias_median_file, folder=slot))

        # Persist the png files.
        metadata = dict(CCD_MANU=ccd_vendor, LSST_NUM=sensor_id,
                        TESTTYPE='FE55', TEST_CATEGORY='EO')
        results.extend(siteUtils.persist_png_files('%s*.png' % sensor_id,
                                                   sensor_id, folder=slot,
                                                   metadata=metadata))

        data = sensorTest.EOTestResults(gain_file)
        amps = data['AMP']
        gain_data = data['GAIN']
        gain_errors = data['GAIN_ERROR']
        sigmas = data['PSF_SIGMA']
        for amp, gain_value, gain_error, sigma in zip(amps, gain_data,
                                                      gain_errors, sigmas):
            if not np.isfinite(gain_error):
                gain_error = -1
            results.append(lcatr.schema.valid(
                lcatr.schema.get('fe55_raft_analysis'),
                amp=amp, gain=gain_value,
                gain_error=gain_error,
                psf_sigma=sigma,
                slot=slot,
                sensor_id=sensor_id))

        results.extend([lcatr.schema.fileref.make(x) for x in output_files])
    return results


if __name__ == '__main__':
    if os.environ.get("LCATR_SKIP_FE55_ANALYSIS", "False") == "True":
        results = persist_fe55_gains()
    else:
        results = persist_fe55_analysis_results()

    results.extend(siteUtils.jobInfo())

    lcatr.schema.write_file(results)
    lcatr.schema.validate_file()
