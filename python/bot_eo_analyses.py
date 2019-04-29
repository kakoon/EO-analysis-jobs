"""
Producer script for BOT analyses.
"""
from __future__ import print_function
import os
import glob
import copy
import pickle
import configparser
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
import lsst.eotest.image_utils as imutils
import lsst.eotest.sensor as sensorTest
import lsst.eotest.raft as raftTest
import eotestUtils
import siteUtils
from correlated_noise import correlated_noise, raft_level_oscan_correlations
from camera_components import camera_info
from tearing_detection import tearing_detection
from multiprocessor_execution import run_device_analysis_pool

__all__ = ['run_det_task_analysis', 'make_file_prefix',
           'fe55_task', 'fe55_jh_task',
           'bias_frame_task', 'bias_frame_jh_task',
           'scan_mode_analysis_task', 'scan_mode_analysis_jh_task',
           'read_noise_task', 'read_noise_jh_task',
           'raft_noise_correlations', 'raft_jh_noise_correlations',
           'bright_defects_task', 'bright_defects_jh_task',
           'dark_defects_task', 'dark_defects_jh_task',
           'traps_task', 'traps_jh_task',
           'dark_current_task', 'dark_current_jh_task',
           'plot_ccd_total_noise',
           'cte_task', 'cte_jh_task', 'plot_cte_results',
           'find_flat2_bot',
           'flat_pairs_task', 'flat_pairs_jh_task',
           'ptc_task', 'ptc_jh_task',
           'bf_task', 'bf_jh_task',
           'qe_task', 'qe_jh_task',
           'tearing_task', 'tearing_jh_task',
           'raft_results_task', 'repackage_summary_files',
           'get_analysis_types', 'mondiode_value',
           'GlobPattern']


class GlobPattern:
    """Functor class to return glob patterns for finding BOT_acq data."""
    def __init__(self):
        config = configparser.ConfigParser(inline_comment_prefixes=("#", ))
        config.optionxform = str
        default_config = os.path.join(os.environ['EOANALYSISJOBSDIR'],
                                      'data', 'BOT_jh_glob_patterns.ini')
        cfg_file = os.environ.get('LCATR_JH_GLOB_PATTERN_FILE', default_config)
        config.read(cfg_file)
        self.task_patterns = {k: v for k, v in config.items('BOT_acq')}

    def __call__(self, task, det_name):
        pattern = self.task_patterns[task]
        return '{}/*_{}.fits'.format(pattern, det_name)


glob_pattern = GlobPattern()


def make_file_prefix(run, component_name):
    """
    Compose the run number and component name into string prefix
    to use with filenames.
    """
    return "{}_{}".format(component_name, run)


def bias_filename(file_prefix, check_is_file=True):
    """
    Name of bias frame file derived from stacked bias files.
    """
    filename = '{}_median_bias.fits'.format(file_prefix)
    if check_is_file and not os.path.isfile(filename):
        # Look for bias file from prerequisite job.
        return siteUtils.dependency_glob(filename)[0]
    return filename


def fe55_jh_task(det_name):
    "JH version of single sensor execution of the Fe55 analysis task."
    run = siteUtils.getRunNumber()
    acq_jobname = siteUtils.getProcessName('BOT_acq')
    nbias = os.environ.get('LCATR_NUM_BIAS_FRAMES', 25)

    fe55_files = siteUtils.dependency_glob(glob_pattern('fe55', det_name),
                                           acq_jobname=acq_jobname)
    bias_files = siteUtils.dependency_glob(glob_pattern('fe55_bias', det_name),
                                           acq_jobname=acq_jobname)[:nbias]
    if not fe55_files or not bias_files:
        print("fe55_task: Needed data files missing for detector", det_name)
        return None
    return fe55_task(run, det_name, fe55_files, bias_files)


def fe55_task(run, det_name, fe55_files, bias_files):
    "Single sensor execution of the Fe55 analysis task."
    file_prefix = make_file_prefix(run, det_name)
    title = '{}, {}'.format(run, det_name)

    bias_frame = bias_filename(file_prefix)
    png_files = []

    try:
        pixel_stats = sensorTest.Fe55PixelStats(fe55_files,
                                                sensor_id=file_prefix)
        png_files.append('%s_fe55_p3_p5_hists.png' % file_prefix)
        siteUtils.make_png_file(pixel_stats.pixel_hists, png_files[-1],
                                pix0='p3', pix1='p5')

        png_files.append('%s_fe55_p3_p5_profiles.png' % file_prefix)
        siteUtils.make_png_file(pixel_stats.pixel_diff_profile,
                                png_files[-1], pixel_coord='x',
                                pix0='p3', pix1='p5')

    except:
        # Encountered error processing data or generating pngs so skip
        # these plots.
        pass

    rolloff_mask_file = '%s_edge_rolloff_mask.fits' % file_prefix
    sensorTest.rolloff_mask(fe55_files[0], rolloff_mask_file)

    hist_nsig = 20

    task = sensorTest.Fe55Task()
    task.config.temp_set_point = -100.
    task.run(file_prefix, fe55_files, (rolloff_mask_file,),
             bias_frame=bias_frame, accuracy_req=0.01, hist_nsig=hist_nsig)

    # Fe55 gain and psf analysis results plots for the test report.
    results_file = '%s_eotest_results.fits' % file_prefix
    plots = sensorTest.EOTestPlots(file_prefix, results_file=results_file)

    png_files.append('%s_gains.png' % file_prefix)
    siteUtils.make_png_file(plots.gains, png_files[-1])

    png_files.append('%s_fe55_median_bias.png' % file_prefix)
    siteUtils.make_png_file(sensorTest.plot_flat, png_files[-1], bias_frame,
                            title='%s, median bias frame' % title,
                            annotation='ADU/pixel, overscan-subtracted')

    fe55_file = glob.glob('%s_psf_results*.fits' % file_prefix)[0]
    png_files.append('%s_fe55_dists.png' % file_prefix)
    siteUtils.make_png_file(plots.fe55_dists, png_files[-1],
                            fe55_file=fe55_file, xrange_scale=5,
                            hist_nsig=hist_nsig)

    png_files.append('%s_psf_dists.png' % file_prefix)
    siteUtils.make_png_file(plots.psf_dists, png_files[-1],
                            fe55_file=fe55_file)

    png_file_list = '{}_fe55_task_png_files.txt'.format(det_name)
    with open(png_file_list, 'w') as output:
        for item in png_files:
            if os.path.isfile(item):
                output.write('{}\n'.format(item))


def get_amplifier_gains(file_pattern=None):
    """Extract the gains for each amp in an eotest_results file."""
    if (os.environ.get('LCATR_USE_UNIT_GAINS', 'False') == 'True'
        or file_pattern is None):
        return {amp: 1 for amp in range(1, 17)}

    # Attempt to retrieve gains from fe55_analysis_BOT then ptc_BOT.
    # If neither are available, then use unit gains.
    results_files = siteUtils.dependency_glob(file_pattern,
                                              jobname='fe55_analysis_BOT')
    if not results_files:
        results_files = siteUtils.dependency_glob(file_pattern,
                                                  jobname='ptc_BOT')
    if not results_files:
        return {amp: 1 for amp in range(1, 17)}

    eotest_results_file = results_files[0]
    data = sensorTest.EOTestResults(eotest_results_file)
    amps = data['AMP']
    gains = data['GAIN']
    return {amp: gain for amp, gain in zip(amps, gains)}


def bias_frame_jh_task(det_name):
    """JH version of the bias_frame_task."""
    run = siteUtils.getRunNumber()
    acq_jobname = siteUtils.getProcessName('BOT_acq')
    nbias = os.environ.get('LCATR_NUM_BIAS_FRAMES', 10)
    bias_files \
        = siteUtils.dependency_glob(glob_pattern('bias_frame', det_name),
                                    acq_jobname=acq_jobname)[:nbias]
    if not bias_files:
        print("bias_frame_task: Needed data files are missing for detector",
              det_name)
        return None
    return bias_frame_task(run, det_name, bias_files)


def bias_frame_task(run, det_name, bias_files):
    """Create a median bias file for use by downstream tasks."""
    file_prefix = make_file_prefix(run, det_name)
    bias_frame = bias_filename(file_prefix, check_is_file=False)
    amp_geom = sensorTest.makeAmplifierGeometry(bias_files[0])
    imutils.superbias_file(bias_files, amp_geom.serial_overscan, bias_frame)


def scan_mode_analysis_jh_task(det_name):
    """JH version of scan mode analysis task."""
    run = siteUtils.getRunNumber()
    scan_mode_files = []
    return scan_mode_analysis_task(run, det_name, scan_mode_files)


def scan_mode_analysis_task(run, det_name, scan_mode_files):
    """Scan mode analysis task."""
    file_prefix = make_file_prefix(run, det_name)
    # TODO: Implement scan mode analysis.


def read_noise_jh_task(det_name):
    """JH version of the single sensor read noise task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')
    nbias = os.environ.get('LCATR_NUM_BIAS_FRAMES', 10)

    bias_files \
        = siteUtils.dependency_glob(glob_pattern('read_noise', det_name),
                                    acq_jobname=acq_jobname)[:nbias]
    if not bias_files:
        print("read_noise_task: Needed data files are missing for detector",
              det_name)
        return None
    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))

    return read_noise_task(run, det_name, bias_files, gains,
                           mask_files=mask_files)


def read_noise_task(run, det_name, bias_files, gains, mask_files=(),
                    system_noise=None):
    """Run the read noise tasks on a single detector."""
    file_prefix = make_file_prefix(run, det_name)
    title = '{}, {}'.format(run, det_name)

    task = sensorTest.ReadNoiseTask()
    task.config.temp_set_point = -100.
    task.run(file_prefix, bias_files, gains, system_noise=system_noise,
             mask_files=mask_files, use_overscan=True)

    # Compute amp-amp correlated noise.
    my_bias_files = copy.deepcopy(bias_files)
    _, corr_fig, _ = correlated_noise(my_bias_files, target=0,
                                      make_plots=True, title=title)
    plt.figure(corr_fig.number)
    plt.savefig('%s_correlated_noise.png' % file_prefix)


def raft_jh_noise_correlations(raft_name):
    """JH version of raft-level noise-correlation analysis."""
    run = siteUtils.getRunNumber()
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    bias_files \
        = siteUtils.dependency_glob(glob_pattern('raft_noise_correlations',
                                                 '{}_S??'.format(raft_name)),
                                    acq_jobname=acq_jobname)
    if not bias_files:
        print("raft_noise_correlations: Missing bias files for raft",
              raft_name)
        return None
    bias_file_dict = dict()
    slot_names = camera_info.get_slot_names()
    for item in bias_files:
        for slot_name in slot_names:
            if slot_name in bias_file_dict:
                continue
            det_name = '{}_{}'.format(raft_name, slot_name)
            if det_name in os.path.basename(item):
                bias_file_dict[slot_name] = item
    return raft_noise_correlations(run, raft_name, bias_file_dict)


def raft_noise_correlations(run, raft_name, bias_file_dict):
    """Raft-level noise-correlation analysis."""
    file_prefix = make_file_prefix(run, raft_name)
    title = "Overscan correlations, Run {}, {}".format(run, raft_name)
    raft_level_oscan_correlations(bias_file_dict, title=title)
    plt.savefig('{}_overscan_correlations.png'.format(file_prefix))


def bright_defects_jh_task(det_name):
    """JH version of single sensor bright pixels task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    dark_files \
        = siteUtils.dependency_glob(glob_pattern('bright_defects', det_name),
                                    acq_jobname=acq_jobname)
    if not dark_files:
        print("bright_defects_task: Needed data files missing for detector",
              det_name)
        return None

    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)
    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))

    bias_frame = bias_filename(file_prefix)

    return bright_defects_task(run, det_name, dark_files, gains,
                               mask_files=mask_files, bias_frame=bias_frame)


def bright_defects_task(run, det_name, dark_files, gains, mask_files=(),
                        bias_frame=None):
    "Single sensor execution of the bright pixels task."
    file_prefix = make_file_prefix(run, det_name)
    title = '{}, {}'.format(run, det_name)

    task = sensorTest.BrightPixelsTask()
    task.config.temp_set_point = -100.
    task.run(file_prefix, dark_files, mask_files, gains, bias_frame=bias_frame)

    title = '%s, medianed dark for bright defects analysis' % file_prefix
    annotation = 'e-/pixel, gain-corrected, bias-subtracted'
    siteUtils.make_png_file(sensorTest.plot_flat,
                            '%s_medianed_dark.png' % file_prefix,
                            '%s_median_dark_bp.fits' % file_prefix,
                            title=title, annotation=annotation)


def dark_defects_jh_task(det_name):
    """JH version of single sensor execution of the dark defects task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    sflat_files \
        = siteUtils.dependency_glob(glob_pattern('dark_defects', det_name),
                                    acq_jobname=acq_jobname)
    if not sflat_files:
        print("dark_defects_task: No high flux superflat files found for",
              det_name)
        return None

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    bias_frame = bias_filename(file_prefix)

    return dark_defects_task(run, det_name, sflat_files, mask_files=mask_files,
                             bias_frame=bias_frame)


def dark_defects_task(run, det_name, sflat_files, mask_files=(),
                      bias_frame=None):
    """Single sensor execution of the dark defects task."""
    file_prefix = make_file_prefix(run, det_name)
    title = '{}, {}'.format(run, det_name)

    task = sensorTest.DarkPixelsTask()
    task.run(file_prefix, sflat_files, mask_files, bias_frame=bias_frame)

    title = '%s, superflat for dark defects analysis' % file_prefix
    siteUtils.make_png_file(sensorTest.plot_flat,
                            '%s_superflat_dark_defects.png' % file_prefix,
                            '%s_median_sflat.fits' % file_prefix,
                            title=title, annotation='ADU/pixel')

def traps_jh_task(det_name):
    """JH version of single sensor execution of the traps analysis task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    trap_files = siteUtils.dependency_glob(glob_pattern('traps', det_name),
                                           acq_jobname=acq_jobname)
    if not trap_files:
        print("traps_task: No pocket pumping file found for detector",
              det_name)
        return None
    trap_file = trap_files[0]

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))

    # Omit rolloff defects mask since a trap in the rolloff edge region can
    # affect the entire column.
    mask_files \
        = [item for item in mask_files if item.find('edge_rolloff') == -1]

    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)

    bias_frame = bias_filename(file_prefix)

    return traps_task(run, det_name, trap_file, gains, mask_files=mask_files,
                      bias_frame=bias_frame)


def traps_task(run, det_name, trap_file, gains, mask_files=(), bias_frame=None):
    """Single sensor execution of the traps analysis task."""
    file_prefix = make_file_prefix(run, det_name)
    task = sensorTest.TrapTask()
    task.run(file_prefix, trap_file, mask_files, gains, bias_frame=bias_frame)


def dark_current_jh_task(det_name):
    """JH version of single sensor execution of the dark current task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    dark_files \
        = siteUtils.dependency_glob(glob_pattern('dark_current', det_name),
                                    acq_jobname=acq_jobname)
    if not dark_files:
        print("dark_current_task: No dark files found for detector", det_name)
        return None

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    eotest_results_file \
        = siteUtils.dependency_glob('{}_eotest_results.fits'.format(file_prefix),
                                    jobname='read_noise_BOT')[0]
    gains = get_amplifier_gains('{}_eotest_results.fits'.format(file_prefix))
    bias_frame = bias_filename(file_prefix)

    dark_curr_pixels, dark95s \
        = dark_current_task(run, det_name, dark_files, gains,
                            mask_files=mask_files, bias_frame=bias_frame)
    plot_ccd_total_noise(run, det_name, dark_curr_pixels, dark95s,
                         eotest_results_file)
    return dark_curr_pixels, dark95s


def dark_current_task(run, det_name, dark_files, gains, mask_files=(),
                      temp_set_point=-100., bias_frame=None):
    """Single sensor execution of the dark current task."""
    file_prefix = make_file_prefix(run, det_name)
    task = sensorTest.DarkCurrentTask()
    task.config.temp_set_point = temp_set_point
    return task.run(file_prefix, dark_files, mask_files, gains,
                    bias_frame=bias_frame)


def plot_ccd_total_noise(run, det_name, dark_curr_pixels, dark95s,
                         eotest_results_file):
    """
    Make CCD-level total noise summary plots using the dark current
    measurements and an existing eotest results file containing
    the read noise measurements.
    """
    file_prefix = make_file_prefix(run, det_name)
    eo_results = sensorTest.EOTestResults(eotest_results_file)
    read_noise = dict(pair for pair in zip(eo_results['AMP'],
                                           eo_results['TOTAL_NOISE']))
    siteUtils.make_png_file(sensorTest.total_noise_histograms,
                            '%s_total_noise_hists.png' % file_prefix,
                            dark_curr_pixels, read_noise, dark95s,
                            exptime=16, title=det_name)
    plots = sensorTest.EOTestPlots(det_name, results_file=eotest_results_file)
    siteUtils.make_png_file(plots.total_noise, '%s_noise.png' % file_prefix,
                            dark95s=dark95s)


def cte_jh_task(det_name):
    """JH version of single sensor execution of the CTE task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    sflat_high_files \
        = siteUtils.dependency_glob(glob_pattern('cte_high', det_name),
                                    acq_jobname=acq_jobname)
    sflat_low_files \
        = siteUtils.dependency_glob(glob_pattern('cte_low', det_name),
                                    acq_jobname=acq_jobname)
    if not sflat_high_files and not sflat_low_files:
        print("cte_task: Superflat files not found for detector", det_name)
        return None

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))

    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)

    bias_frame = bias_filename(file_prefix)

    # Omit rolloff defects mask since it would mask some of the edges used
    # in the eper method.
    mask_files \
        = [item for item in mask_files if item.find('edge_rolloff') == -1]

    png_files = []
    for flux_level, sflat_files in zip(('high', 'low'),
                                       (sflat_high_files, sflat_low_files)):
        superflat_file = cte_task(run, det_name, sflat_files, gains,
                                  mask_files=mask_files, flux_level=flux_level,
                                  bias_frame=bias_frame)

        png_files.extend(plot_cte_results(run, det_name, superflat_file,
                                          eotest_results_file,
                                          mask_files=mask_files))

    png_file_list = '{}_cte_task_png_files.txt'.format(det_name)
    with open(png_file_list, 'w') as output:
        for item in png_files:
            if os.path.isfile(item):
                output.write('{}\n'.format(item))

    return None


def cte_task(run, det_name, sflat_files, gains, mask_files=(),
             flux_level='high', bias_frame=None):
    """Single sensor execution of the CTE task."""
    file_prefix = make_file_prefix(run, det_name)

    task = sensorTest.CteTask()
    task.run(file_prefix, sflat_files, flux_level=flux_level, gains=gains,
             mask_files=mask_files, bias_frame=bias_frame)
    # TODO: refactor CteTask to provide access to the superflat filename
    # instead of recomputing it here.
    superflat_file = '{}_superflat_{}.fits'.format(file_prefix, flux_level)
    return superflat_file


def plot_cte_results(run, det_name, superflat_file, eotest_results_file,
                     mask_files=()):
    """
    Create single CCD superflat mosaic plots and plots of the serial and
    parallel CTE profiles.
    """
    file_prefix = make_file_prefix(run, det_name)
    flux_level = 'low' if 'low' in os.path.basename(superflat_file) else 'high'
    plots \
        = sensorTest.EOTestPlots(file_prefix, results_file=eotest_results_file)

    png_files = []
    png_files.append(superflat_file.replace('.fits', '.png'))
    siteUtils.make_png_file(sensorTest.plot_flat, png_files[-1],
                            superflat_file,
                            title=('%s, %s, CTE supeflat, %s flux '
                                   % (run, det_name, flux_level)),
                            annotation='ADU/pixel')

    png_files.append('%s_serial_oscan_%s.png' % (file_prefix, flux_level))
    siteUtils.make_png_file(plots.cte_profiles, png_files[-1], flux_level,
                            superflat_file, mask_files, serial=True)

    png_files.append('%s_parallel_oscan_%s.png' % (file_prefix, flux_level))
    siteUtils.make_png_file(plots.cte_profiles, png_files[-1], flux_level,
                            superflat_file, mask_files, serial=False)

    return png_files


def find_flat2_bot(file1):
    """
    Function to find the flat2 file corresponding to the flat1 frame
    for BOT-level acquisitions.
    """
    basename_pattern = '*_' + file1[-len('R22_S11.fits'):]
    pattern = os.path.join(file1.split('flat1')[0] + 'flat0*',
                           basename_pattern)
    try:
        flat2 = glob.glob(pattern)[0]
    except IndexError:
        pattern = os.path.join(file1.split('flat1')[0] + 'flat2*',
                               basename_pattern)
        flat2 = glob.glob(pattern)[0]
    return flat2


def flat_pairs_jh_task(det_name):
    """JH version of single sensor execution of the flat pairs task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    flat_files \
        = siteUtils.dependency_glob(glob_pattern('flat_pairs', det_name),
                                    acq_jobname=acq_jobname)
    if not flat_files:
        print("flat_pairs_task: Flat pairs files not found for detector",
              det_name)
        return None

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    try:
        eotest_results_file \
            = siteUtils.dependency_glob('{}_eotest_results.fits'.format(file_prefix),
                                        jobname='fe55_analysis_BOT')[0]
    except IndexError:
        print("flat_pairs_jh_task: Fe55 eotest results file not found for ",
              file_prefix, ".  Using unit gains.")
        eotest_results_file = None
    gains = get_amplifier_gains(eotest_results_file)
    bias_frame = bias_filename(file_prefix)

    return flat_pairs_task(run, det_name, flat_files, gains,
                           mask_files=mask_files, bias_frame=bias_frame,
                           mondiode_func=mondiode_value)


def flat_pairs_task(run, det_name, flat_files, gains, mask_files=(),
                    flat2_finder=find_flat2_bot,
                    linearity_spec_range=(1e4, 9e4), use_exptime=False,
                    bias_frame=None, mondiode_func=None):
    """Single sensor execution of the flat pairs task."""
    file_prefix = make_file_prefix(run, det_name)

    task = sensorTest.FlatPairTask()
    task.run(file_prefix, flat_files, mask_files, gains,
             linearity_spec_range=linearity_spec_range,
             use_exptime=use_exptime, flat2_finder=flat2_finder,
             bias_frame=bias_frame, mondiode_func=mondiode_func)

    results_file = '%s_eotest_results.fits' % file_prefix
    plots = sensorTest.EOTestPlots(file_prefix, results_file=results_file)

    detresp_file = '%s_det_response.fits' % file_prefix
    siteUtils.make_png_file(plots.linearity,
                            '%s_linearity.png' % file_prefix,
                            detresp_file=detresp_file, max_dev=0.03,
                            use_exptime=use_exptime,
                            Ne_bounds=linearity_spec_range)
    siteUtils.make_png_file(plots.linearity_resids,
                            '%s_linearity_resids.png' % file_prefix,
                            detresp_file=detresp_file, max_dev=0.03,
                            Ne_bounds=linearity_spec_range,
                            use_exptime=use_exptime)


def ptc_jh_task(det_name):
    """JH version of single sensor execution of the PTC task."""
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


def ptc_task(run, det_name, flat_files, gains, mask_files=(),
             flat2_finder=find_flat2_bot, bias_frame=None):
    """Single sensor execution of the PTC task."""
    file_prefix = make_file_prefix(run, det_name)

    task = sensorTest.PtcTask()
    task.run(file_prefix, flat_files, mask_files, gains,
             flat2_finder=flat2_finder, bias_frame=bias_frame)

    results_file = '%s_eotest_results.fits' % file_prefix
    plots = sensorTest.EOTestPlots(file_prefix, results_file=results_file)
    siteUtils.make_png_file(plots.ptcs,
                            '%s_ptcs.png' % file_prefix,
                            ptc_file='%s_ptc.fits' % file_prefix)


def bf_jh_task(det_name):
    """JH version of single sensor execution of the brighter-fatter task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    flat_files \
        = siteUtils.dependency_glob(glob_pattern('brighter_fatter', det_name),
                                    acq_jobname=acq_jobname)

    if not flat_files:
        print("bf_jh_task: Flat pairs files not found for detector", det_name)
        return None

    flat_files = [_ for _ in flat_files if 'flat1' in _]

    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    bias_frame = bias_filename(file_prefix)

    return bf_task(run, det_name, flat_files, mask_files=mask_files,
                   flat2_finder=find_flat2_bot, bias_frame=bias_frame)


def bf_task(run, det_name, flat_files, mask_files=(),
            flat2_finder=None, bias_frame=None):
    """Single sensor execution of the brighter-fatter task."""
    file_prefix = make_file_prefix(run, det_name)

    task = sensorTest.BFTask()
    task.run(file_prefix, flat_files, mask_files=mask_files,
             flat2_finder=flat2_finder, bias_frame=bias_frame)

    results_file = '%s_eotest_results.fits' % file_prefix
    plots = sensorTest.EOTestPlots(file_prefix, results_file=results_file)
    siteUtils.make_png_file(plots.bf_curves,
                            '%s_brighter-fatter.png' % file_prefix,
                            bf_file='%s_bf.fits' % file_prefix)

def qe_jh_task(det_name):
    """JH version of single sensor execution of the QE task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    lambda_files = siteUtils.dependency_glob(glob_pattern('qe', det_name),
                                             acq_jobname=acq_jobname)
    if not lambda_files:
        print("qe_task: QE scan files not found for detector", det_name)
        return None

    pd_ratio_file = eotestUtils.getPhotodiodeRatioFile()
    if pd_ratio_file is None:
        message = ("The BOT photodiode ratio file is " +
                   "not given in config/%s/eotest_calibrations.cfg."
                   % siteUtils.getSiteName())
        raise RuntimeError(message)

#    correction_image = eotestUtils.getIlluminationNonUniformityImage()
#    if correction_image is None:
#        print()
#        print("WARNING: The correction image file is not given in")
#        print("config/%s/eotest_calibrations.cfg." % siteUtils.getSiteName())
#        print("No correction for non-uniform illumination will be applied.")
#        print()
#        sys.stdout.flush()
    mask_files = sorted(glob.glob('{}_*mask.fits'.format(file_prefix)))
    eotest_results_file = '{}_eotest_results.fits'.format(file_prefix)
    gains = get_amplifier_gains(eotest_results_file)
    bias_frame = bias_filename(file_prefix)

    return qe_task(run, det_name, lambda_files, pd_ratio_file, gains,
                   mask_files=mask_files, bias_frame=bias_frame,
                   mondiode_func=mondiode_value)

def qe_task(run, det_name, lambda_files, pd_ratio_file, gains,
            mask_files=(), correction_image=None, temp_set_point=-100,
            bias_frame=None, mondiode_func=None):
    """Single sensor execution of the QE task."""
    file_prefix = make_file_prefix(run, det_name)

    task = sensorTest.QeTask()
    task.config.temp_set_point = temp_set_point
    task.run(file_prefix, lambda_files, pd_ratio_file, mask_files, gains,
             correction_image=correction_image, bias_frame=bias_frame,
             mondiode_func=mondiode_func)

    results_file = '%s_eotest_results.fits' % file_prefix
    plots = sensorTest.EOTestPlots(file_prefix, results_file=results_file)

    siteUtils.make_png_file(plots.qe,
                            '%s_qe.png' % file_prefix,
                            qe_file='%s_QE.fits' % file_prefix)

    try:
        plots.flat_fields(os.path.dirname(lambda_files[0]),
                          annotation='e-/pixel, gain-corrected, bias-subtracted')
    except Exception as eobj:
        print("Exception raised while creating flat fields:")
        print(str(eobj))


def tearing_jh_task(det_name):
    """JH version of single sensor execution of the tearing task."""
    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, det_name)
    acq_jobname = siteUtils.getProcessName('BOT_acq')

    flat_files = siteUtils.dependency_glob(glob_pattern('tearing', det_name),
                                           acq_jobname=acq_jobname)
    if not flat_files:
        print("tearing_task: Flat files not found for detector", det_name)
        return None
    bias_frame = bias_filename(file_prefix)
    return tearing_task(run, det_name, flat_files, bias_frame=bias_frame)

def tearing_task(run, det_name, flat_files, bias_frame=None):
    """Single sensor execution of the tearing task."""
    file_prefix = make_file_prefix(run, det_name)

    tearing_found, _ = tearing_detection(flat_files, bias_frame=bias_frame)
    tearing_stats = [('BOT_EO_acq', 'N/A', det_name, len(tearing_found))]

    with open('%s_tearing_stats.pkl' % file_prefix, 'wb') as output:
        pickle.dump(tearing_stats, output)


def get_raft_files_by_slot(raft_name, file_suffix):
    """Return a dictionary of raft filenames, keyed by slot_name."""
    run = siteUtils.getRunNumber()
    template = '{}_{}_{}_' + file_suffix
    raft_files = dict()
    for slot_name in camera_info.get_slot_names():
        filename = template.format(raft_name, slot_name, run)
        if os.path.isfile(filename):
            raft_files[slot_name] = filename
        else:
            filenames = siteUtils.dependency_glob(filename)
            if filenames:
                raft_files[slot_name] = filenames[0]
    if not raft_files:
        raise FileNotFoundError("no files found for raft %s with suffix %s"
                                % (raft_name, file_suffix))
    return raft_files


def repackage_summary_files():
    """
    Repackage summary.lims files from prior jobs as eotest results
    files.
    """
    run = siteUtils.getRunNumber()
    summary_files = siteUtils.dependency_glob('summary.lims')
    for det_name in camera_info.get_det_names():
        file_prefix = make_file_prefix(run, det_name)
        raft, slot = det_name.split('_')
        repackager = eotestUtils.JsonRepackager()
        repackager.process_files(summary_files, slot=slot, raft=raft)
        repackager.write('{}_eotest_results.fits'.format(file_prefix))


def raft_results_task(raft_name):
    """Task to aggregate data for raft-level plots and results."""
    slot_names = camera_info.get_slot_names()

    # Get results files for each CCD in the raft.
    try:
        results_files \
            = get_raft_files_by_slot(raft_name, 'eotest_results.fits')
    except FileNotFoundError:
        print("No raft-level results for", raft_name)
        return None

    # Determine the total number of pixels and number of edge rolloff
    # pixels for the types of CCDs in this raft and update the results
    # files.  This info will be used in computing the pixel defect
    # compliance.  Use one of the median bias files for this since they
    # should be available no matter which analysis tasks are run.
    bias_frames = get_raft_files_by_slot(raft_name, 'median_bias.fits')
    mask_files = get_raft_files_by_slot(raft_name, 'edge_rolloff_mask.fits')

    total_num, rolloff_mask \
        = sensorTest.pixel_counts(bias_frames[slot_names[0]],
                                  input_mask=mask_files[slot_names[0]])

    # Exposure time (in seconds) for 95th percentile dark current shot
    # noise calculation.
    exptime = 15.

    # Update the eotest results files.
    for filename in results_files.values():
        eotest_results = sensorTest.EOTestResults(filename)
        eotest_results.add_ccd_result('TOTAL_NUM_PIXELS', total_num)
        eotest_results.add_ccd_result('ROLLOFF_MASK_PIXELS', rolloff_mask)
        shot_noise = eotest_results['DARK_CURRENT_95']*exptime
        total_noise = np.sqrt(eotest_results['READ_NOISE']**2 + shot_noise)
        add_max_frac_dev = 'MAX_FRAC_DEV' not in eotest_results.colnames
        for i, amp in enumerate(eotest_results['AMP']):
            if add_max_frac_dev:
                eotest_results.add_seg_result(amp, 'MAX_FRAC_DEV', 0.)
            eotest_results.add_seg_result(amp, 'DC95_SHOT_NOISE',
                                          np.float(shot_noise[i]))
            eotest_results['TOTAL_NOISE'][i] = total_noise[i]
        eotest_results.write(filename)

    run = siteUtils.getRunNumber()
    file_prefix = make_file_prefix(run, raft_name)
    title = '{}, {}'.format(run, raft_name)

    gains = {slot_name: get_amplifier_gains(results_files[slot_name])
             for slot_name in results_files}

    # Extract dark currents for each amplifier in the raft.
    dark_currents = dict()
    for slot_name, results_file in results_files.items():
        results = sensorTest.EOTestResults(results_file)
        dark_currents[slot_name] \
            = dict(_ for _ in zip(results['AMP'],
                                  results['DARK_CURRENT_MEDIAN']))

    png_files = []
    # Median bias mosaic
    median_bias = raftTest.RaftMosaic(bias_frames, bias_subtract=False)
    median_bias.plot(title='%s, median bias frames' % title,
                     annotation='ADU/pixel', rotate180=True)
    png_files.append('{}_median_bias.png'.format(file_prefix))
    plt.savefig(png_files[-1])
    del median_bias

    # Dark mosaic
    dark_files = get_raft_files_by_slot(raft_name, 'median_dark_bp.fits')
    dark_mosaic = raftTest.RaftMosaic(dark_files, gains=gains,
                                      bias_frames=bias_frames)
    dark_mosaic.plot(title='{}, medianed dark frames'.format(title),
                     annotation='e-/pixel, gain-corrected, bias-subtracted',
                     rotate180=True)
    png_files.append('{}_medianed_dark.png'.format(file_prefix))
    plt.savefig(png_files[-1])
    del dark_mosaic

    # High flux superflat mosaic.
    try:
        sflat_high_files \
            = get_raft_files_by_slot(raft_name, 'superflat_high.fits')
    except FileNotFoundError as eobj:
        print(eobj)
    else:
        sflat_high = raftTest.RaftMosaic(sflat_high_files, gains=gains,
                                         bias_frames=bias_frames,
                                         dark_currents=dark_currents)
        sflat_high.plot(title='%s, high flux superflat' % title,
                        annotation='e-/pixel, gain-corrected, bias-subtracted',
                        rotate180=True)
        png_files.append('{}_superflat_high.png'.format(file_prefix))
        plt.savefig(png_files[-1])
        del sflat_high

    # Low flux superflat mosaic.
    try:
        sflat_low_files \
            = get_raft_files_by_slot(raft_name, 'superflat_low.fits')
    except FileNotFoundError as eobj:
        print(eobj)
    else:
        sflat_low = raftTest.RaftMosaic(sflat_low_files, gains=gains,
                                        bias_frames=bias_frames,
                                        dark_currents=dark_currents)
        sflat_low.plot(title='%s, low flux superflat' % title,
                       annotation='e-/pixel, gain-corrected, bias-subtracted',
                       rotate180=True)
        png_files.append('{}_superflat_low.png'.format(file_prefix))
        plt.savefig(png_files[-1])
        del sflat_low

    # QE images at various wavelengths and filters
    acq_jobname = siteUtils.getProcessName('BOT_acq')
    for wl in ('SDSSu', 'SDSSg', 'SDSSr', 'SDSSi', 'SDSSz', 'SDSSY',
               '480nm', '650nm', '750nm', '870nm', '950nm', '970nm'):
        print("Processing %s image" % wl)
        pattern = 'lambda_flat_{}*/*_{}_*.fits'.format(wl, raft_name)
        print(pattern)
        print(acq_jobname)
        files = siteUtils.dependency_glob(pattern, acq_jobname=acq_jobname)
        if not files:
            print("no files found")
            continue
        lambda_files = dict()
        for item in files:
            slot_name = os.path.basename(item).split('_')[-1].split('.')[0]
            lambda_files[slot_name] = item
        flat = raftTest.RaftMosaic(lambda_files, gains=gains,
                                   bias_frames=bias_frames,
                                   dark_currents=dark_currents)
        flat.plot(title='%s, %s' % (title, wl),
                  annotation='e-/pixel, gain-corrected, bias-subtracted',
                  rotate180=True)
        png_files.append('{}_{}_flat.png'.format(file_prefix, wl))
        plt.savefig(png_files[-1])
        del flat

    # TODO: QE summary plot

    # Plots of read noise, nonlinearity, serial and parallel CTI,
    # PSF size, and gains from Fe55 and PTC.
    spec_plots = raftTest.RaftSpecPlots(results_files)
    columns = 'READ_NOISE DC95_SHOT_NOISE TOTAL_NOISE'.split()
    spec_plots.make_multi_column_plot(columns, 'noise per pixel (-e rms)',
                                      spec=9, title=title, ybounds=(-1, 100))
    png_files.append('%s_total_noise.png' % file_prefix)
    plt.savefig(png_files[-1])

    spec_plots.make_plot('MAX_FRAC_DEV',
                         'non-linearity (max. fractional deviation)',
                         spec=0.03, title=title, ybounds=(0, 0.1))
    png_files.append('%s_linearity.png' % file_prefix)
    plt.savefig(png_files[-1])

    spec_plots.make_multi_column_plot(('CTI_LOW_SERIAL', 'CTI_HIGH_SERIAL'),
                                      'Serial CTI (ppm)', spec=(5e-6, 3e-5),
                                      title=title, yscaling=1e6, yerrors=True,
                                      colors='br', ybounds=(-1e-5, 6e-5))
    png_files.append('%s_serial_cti.png' % file_prefix)
    plt.savefig(png_files[-1])

    spec_plots.make_multi_column_plot(('CTI_LOW_PARALLEL', 'CTI_HIGH_PARALLEL'),
                                      'Parallel CTI (ppm)', spec=3e-6,
                                      title=title, yscaling=1e6, yerrors=True,
                                      colors='br', ybounds=(-1e-5, 6e-5))
    png_files.append('%s_parallel_cti.png' % file_prefix)
    plt.savefig(png_files[-1])

    try:
        spec_plots.make_plot('PSF_SIGMA', 'PSF sigma (microns)', spec=5.,
                             title=title, ybounds=(0, 5.2))
        png_files.append('%s_psf_sigma.png' % file_prefix)
        plt.savefig(png_files[-1])
    except KeyError:
        # PSF_SIGMA not available so skip this plot
        pass

    try:
        spec_plots.make_multi_column_plot(('GAIN', 'PTC_GAIN'),
                                          'System Gain (e-/ADU)',
                                          yerrors=True, title=title,
                                          colors='br', ybounds=(0, 3))
        png_files.append('%s_system_gain.png' % file_prefix)
        plt.savefig(png_files[-1])
    except KeyError:
        # PTC_GAIN data not available so skip this plot.
        pass

    spec_plots.make_plot('DARK_CURRENT_95',
                         '95th percentile dark current (e-/pixel/s)',
                         spec=0.2, title=title, ybounds=(-0.01, 1))
    png_files.append('%s_dark_current.png' % file_prefix)
    plt.savefig(png_files[-1])

    png_file_list = '{}_raft_results_task_png_files.txt'.format(raft_name)
    with open(png_file_list, 'w') as output:
        for item in png_files:
            if os.path.isfile(item):
                output.write('{}\n'.format(item))

    return None


def get_analysis_types(bot_eo_config_file=None):
    """"Get the analysis types to be performed from the BOT-level EO config."""
    if bot_eo_config_file is None:
        # Find the BOT-level EO configuration file.
        acq_cfg = os.path.join(os.environ['LCATR_CONFIG_DIR'], 'acq.cfg')
        with open(acq_cfg, 'r') as fd:
            for line in fd:
                if line.startswith('bot_eo_acq_cfg'):
                    bot_eo_config_file = line.strip().split('=')[1].strip()
                    break

    # Read in the analyses to be performed from the config file.
    cp = configparser.ConfigParser(allow_no_value=True,
                                   inline_comment_prefixes=("#", ))
    cp.optionxform = str   # allow for case-sensitive keys
    cp.read(bot_eo_config_file)

    analysis_types = []
    for analysis_type, _ in cp.items("ANALYZE"):
        analysis_types.append(analysis_type)

    return analysis_types


def mondiode_value(flat_file, exptime, factor=5,
                   pd_filename='Photodiode_Readings.txt'):
    """
    Compute the mean current measured by the monitoring photodiode.

    Parameters
    ----------
    flat_file: str
        Path to the flat frame FITS file.   The pd data file
        is assumed to be in the same directory.
    exptime: float
        Exposure time in seconds.
    factor: float [5]
        Factor to use to extract the baseline current values from the
        data using ythresh = (min(y) + max(y))/factor + min(y)
    pd_filename: str ['Photodiode_Readings.txt']
        Basename of photodiode readings file.

    Returns
    -------
    float: The mean current.
    """
    # Try reading the MONDIODE keyword first.
    with fits.open(flat_file) as hdulist:
        if 'MONDIODE' in hdulist[0].header:
            return hdulist[0].header['MONDIODE']

    # Compute the value from the photodiode readings file.
    pd_file = os.path.join(os.path.dirname(flat_file), pd_filename)
    x, y = np.recfromtxt(pd_file).transpose()
    # Threshold for finding baseline current values:
    ythresh = (min(y) + max(y))/factor + min(y)
    # Subtract the median of the baseline values to get a calibrated
    # current.
    y -= np.median(y[np.where(y < ythresh)])
    integral = sum((y[1:] + y[:-1])/2*(x[1:] - x[:-1]))
    return integral/exptime


det_task_mapping = {'gain': (fe55_jh_task,),
                    'bias': (bias_frame_jh_task,),
                    'scan': (scan_mode_analysis_jh_task),
                    'biasnoise': (read_noise_jh_task,),
                    'dark': (dark_current_jh_task,),
                    'badpixel': (bright_defects_jh_task, dark_defects_jh_task),
                    'ptc': (ptc_jh_task,),
                    'brighterfatter': (bf_jh_task,),
                    'linearity': (flat_pairs_jh_task,),
                    'cti': (cte_jh_task,),
                    'tearing': (tearing_jh_task,),
                    'traps': (traps_jh_task,)}


def run_det_task_analysis(det_task_name, det_names=None, processes=None):
    """Run the desired detector-level task using multiprocessing."""
    tasks = det_task_mapping[det_task_name]

    if det_names is None:
        det_names = camera_info.get_det_names()

    if det_task_name in get_analysis_types():
        for task in tasks:
            run_device_analysis_pool(task, det_names, processes=processes)
