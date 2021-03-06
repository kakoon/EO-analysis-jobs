#!/usr/bin/env ipython
"""
Producer script for raft-level flat pairs analysis.
"""

def run_tearing_detection(sensor_id):
    """
    Loop over the acquisition jobs and perform tearing analysis on each.
    """
    import pickle
    import lsst.eotest.image_utils as imutils
    import lsst.eotest.sensor as sensorTest
    import siteUtils
    from tearing_detection import tearing_detection

    file_prefix = '%s_%s' % (sensor_id, siteUtils.getRunNumber())
    tearing_stats = []
    # Create a super bias frame.
    bias_files = siteUtils.dependency_glob('S*/%s_flat_bias*.fits' % sensor_id,
                                           jobname=siteUtils.getProcessName('flat_pair_raft_acq'),
                                           description='Bias files:')
    if bias_files:
        bias_frame = '%s_superbias.fits' % sensor_id
        amp_geom = sensorTest.makeAmplifierGeometry(bias_files[0])
        imutils.superbias_file(bias_files[:10], amp_geom.serial_overscan,
                               bias_frame)
    else:
        bias_frame = None

    acq_jobs = {('flat_pair_raft_acq', 'N/A'): 'S*/%s_flat*flat?_*.fits',
                ('qe_raft_acq', 'N/A'): 'S*/%s_lambda_flat_*.fits',
                ('sflat_raft_acq', 'low_flux'): 'S*/%s_sflat_500_flat_L*.fits',
                ('sflat_raft_acq', 'high_flux'): 'S*/%s_sflat_500_flat_H*.fits'}
    for job_key, pattern in acq_jobs.items():
        job_name, subset = job_key
        flats = siteUtils.dependency_glob(pattern % sensor_id,
                                          jobname=siteUtils.getProcessName(job_name),
                                          description='Flat files:')
        tearing_found, _ = tearing_detection(flats, bias_frame=bias_frame)
        tearing_stats.append((job_name, subset, sensor_id, len(tearing_found)))

    with open('%s_tearing_stats.pkl' % file_prefix, 'wb') as output:
        pickle.dump(tearing_stats, output)


if __name__ == '__main__':
    import os
    import json
    import matplotlib.pyplot as plt
    import siteUtils
    import camera_components
    import lsst.eotest.raft as raftTest
    from multiprocessor_execution import sensor_analyses

    processes = 9                # Reserve 1 process per CCD.
    sensor_analyses(run_tearing_detection, processes=processes)

    # Divisidero tearing analysis.
    run = siteUtils.getRunNumber()
    raft_unit_id = siteUtils.getUnitId()
    files = siteUtils.dependency_glob('*median_sflat.fits',
                                      jobname='dark_defects_raft',
                                      description='Superflat files:')
    raft = camera_components.Raft.create_from_etrav(raft_unit_id,
                                                    db_name='Prod')
    det_map = dict([(sensor_id, slot) for slot, sensor_id in raft.items()])

    sflat_files = dict()
    for item in files:
        slot = det_map[os.path.basename(item).split('_')[0]]
        sflat_files[slot] = item

    max_divisidero_tearing \
        = raftTest.ana_divisidero_tearing(sflat_files, raft_unit_id, run)
    plt.savefig(f'{raft_unit_id}_{run}_divisidero.png')

    with open(f'{raft_unit_id}_{run}_max_divisidero.json', 'w') as fd:
        json.dump(max_divisidero_tearing, fd)
