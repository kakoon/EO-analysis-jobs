#!/usr/bin/env python
"""
Script to collect the EO analysis results for each sensor and write
an eotest_report.fits file.  Also create raft-level mosaics.
"""
from __future__ import print_function
import os
from collections import OrderedDict
import matplotlib.pyplot as plt
import lsst.eotest.sensor as sensorTest
import lsst.eotest.raft as raftTest
from lcatr.harness.helpers import dependency_glob
import eotestUtils
import siteUtils
import camera_components

def slot_dependency_glob(pattern, jobname):
    "Return an OrderedDict of files with the desired pattern, keyed by slot."
    files = sorted(siteUtils.dependency_glob(os.path.join('S??', pattern),
                                             jobname=jobname))
    return OrderedDict([(fn.split('/')[-2], fn) for fn in files])

# Use a mean bias file to determine the maximum number of active
# pixels for the image quality statistics.
bias_files = slot_dependency_glob('*_mean_bias_*.fits', 'fe55_raft_analysis')
total_num, rolloff_mask = sensorTest.pixel_counts(bias_files.values()[0])

raft_id = siteUtils.getUnitId()
raft = camera_components.Raft.create_from_etrav(raft_id)
summary_files = dependency_glob('summary.lims')
results_files = dict()
for slot, sensor_id in raft.items():
    # Aggregate information from summary.lims files into a final
    # EOTestResults output file for the desired sensor_id.
    repackager = eotestUtils.JsonRepackager()
    repackager.eotest_results.add_ccd_result('TOTAL_NUM_PIXELS', total_num)
    repackager.eotest_results.add_ccd_result('ROLLOFF_MASK_PIXELS',
                                             rolloff_mask)
    repackager.process_files(summary_files, sensor_id=sensor_id)

    outfile = '%s_eotest_results.fits' % sensor_id
    repackager.write(outfile)
    results_files[slot] = outfile

gains = dict()
for slot, res_file in results_files.items():
    results = sensorTest.EOTestResults(res_file)
    gains[slot] = dict([(amp, gain) for amp, gain
                        in zip(results['AMP'], results['GAIN'])])

# Raft-level mosaics of median darks, bias, superflats high and low.
dark_mosaic = raftTest.RaftMosaic(slot_dependency_glob('*median_dark_bp.fits',
                                                       'bright_defects_raft'),
                                  gains=gains)
dark_mosaic.plot(title='%s, medianed dark frames' % raft_id)
plt.savefig('%s_medianed_dark.png' % raft_id)
del dark_mosaic

mean_bias = raftTest.RaftMosaic(bias_files)
mean_bias.plot(title='%s, mean bias frames' % raft_id)
plt.savefig('%s_mean_bias.png' % raft_id)
del mean_bias

sflat_high = raftTest.RaftMosaic(slot_dependency_glob('*superflat_high.fits',
                                                      'cte_raft'), gains=gains)
sflat_high.plot(title='%s, high flux superflat' % raft_id)
plt.savefig('%s_superflat_high.png' % raft_id)
del sflat_high

sflat_low = raftTest.RaftMosaic(slot_dependency_glob('*superflat_low.fits',
                                                     'cte_raft'), gains=gains)
sflat_low.plot(title='%s, low flux superflat' % raft_id)
plt.savefig('%s_superflat_low.png' % raft_id)
del sflat_low

# QE images at 350, 500, 620, 750, 870, and 1000 nm.
for wl in (350, 500, 620, 750, 870, 1000):
    print("Processing %i nm image" % wl)
    files = slot_dependency_glob('*lambda_flat_%04i_*.fits' % wl,
                                 siteUtils.getProcessName('qe_raft_acq'))
    try:
        flat = raftTest.RaftMosaic(files, gains=gains)
        flat.plot(title='%s, %i nm' % (raft_id, wl))
        plt.savefig('%s_%04inm_flat.png' % (raft_id, wl))
        del flat
    except IndexError as eobj:
        print(files)
        print(eobj)

# Raft-level bar charts of read noise, nonlinearity, serial and parallel CTI,
# charge diffusion PSF, and gains from Fe55 and PTC.
bar_charts = raftTest.RaftBarCharts(results_files)

bar_charts.make_bar_chart('READ_NOISE', 'read noise (-e rms)', spec=9,
                          title=raft_id)
plt.savefig('%s_read_noise.png' % raft_id)

bar_charts.make_bar_chart('MAX_FRAC_DEV',
                          'non-linearity (max. fractional deviation)',
                          spec=0.02, title=raft_id)
plt.savefig('%s_linearity.png' % raft_id)

bar_charts.make_multi_bar_chart(('CTI_LOW_SERIAL', 'CTI_HIGH_SERIAL'),
                                'Serial CTI', spec=5e-6, ylog=True,
                                title=raft_id, colors='br')
plt.savefig('%s_serial_cti.png' % raft_id)

bar_charts.make_multi_bar_chart(('CTI_LOW_PARALLEL', 'CTI_HIGH_PARALLEL'),
                                'Parallel CTI', spec=3e-6, ylog=True,
                                title=raft_id, colors='br')
plt.savefig('%s_parallel_cti.png' % raft_id)

bar_charts.make_bar_chart('PSF_SIGMA', 'PSF sigma (microns)', spec=5.,
                          title=raft_id)
plt.savefig('%s_psf_sigma.png' % raft_id)

bar_charts.make_multi_bar_chart(('GAIN', 'PTC_GAIN'), 'System Gain (e-/ADU)',
                                title=raft_id, colors='br')
plt.savefig('%s_system_gain.png' % raft_id)