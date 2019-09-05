import datetime
import gfs_manager
import glob
import os
import settings
import utils



if __name__ == '__main__':
    # Connection to the ftp and checking of the most recent data
    try:
        ftp = utils.connect('grib')
        relevant_subfolder = utils.check_gfs_data(ftp)
    except:
        print('Cannot connect to the ftp site and get content list!')

    # Research of the last update. If the data contained in gfs_data folder are older, it will delete them.
    try:
        utils.delete_last_update(relevant_subfolder)
    except:
        pass

    # Download of the most recent GFS data
    try:
        utils.download_gfs_data(settings.GFS_DATA_DIR, relevant_subfolder)
        print('Download completed!')
    except:
        print('Problems with the download!')

    # Creation of a list of grib data previously downloaded
    gfss = glob.glob(os.path.join(settings.GFS_DATA_DIR, 'gfs_*'))
    gfss.sort(reverse=False)

    # Conversion from grib to bin
    print('Conversion from grib to bin...')
    for gfs in gfss:
        gfsobj = gfs_manager.GFSManager(gfs)
        gfsobj.APCP2bin()
    print('Conversion from grib to bin completed!')

    cumulate_hours = settings.aggregation_intervals
    cumulate_hours.sort(reverse=True)

    start_dt = datetime.datetime.strptime(relevant_subfolder[4:12] + relevant_subfolder[-2:], '%Y%m%d%H').replace(tzinfo=datetime.timezone.utc)

    # The first serie is built from scratch
    agg_interval = cumulate_hours[0]
    print('Working on', str(agg_interval), 'hours accumulation...')
    longest_serie = utils.cumulate(start_dt, agg_interval)
    utils.compare_precip(longest_serie.accumul, agg_interval)

    # The other series are subserie of the previous
    for agg_interval in cumulate_hours[1:]:
        print('Working on', str(agg_interval), 'hours accumulation...')
        duration = datetime.timedelta(hours=agg_interval)
        serie = longest_serie.latest_subserie(duration, agg_interval)
        serie.save_accumul()
        utils.compare_precip(serie.accumul, agg_interval)

    # Saving last update
    update_abspath = os.path.join(settings.GFS_OUTPUT_DIR, settings.UPDATE_FILE)
    with open(update_abspath, 'w') as update_file:
        update_file.write('latest measure ended at:\n')
        update_file.write(serie.start_dt.strftime(settings.DATETIME_FORMAT))