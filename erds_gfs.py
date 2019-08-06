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
        print('Last upgrade:', relevant_subfolder[4:])
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

    # Creation of a list of GRIB data previously downloaded
    gfss = glob.glob(os.path.join(settings.GFS_DATA_DIR, 'gfs_*'))

    # Conversion from GRIB_APCP to bin_APCP
    print('Conversion from GRIB to bin...')
    for gfs in gfss:
        gfsobj = gfs_manager.GFSManager(gfs)
        gfsobj.APCP2bin()
    print('Conversion from grib to bin completed!')

    cumulate_hours = settings.aggregation_intervals
    cumulate_hours.sort(reverse=False)

    for hours in cumulate_hours:
        print('Working on', str(hours), 'hours accumulation... ')
        # Evaluation of accumulated rainfall
        apcp_cum = utils.cumulate(settings.GFS_DATA_DIR, hours)
        # Reverse from 0/360 to -180/+180
        accum_rainfall = utils.reverse_array(apcp_cum)
        # Accumulated rainfall geotiff saving
        tif_abspath = os.path.join(settings.GFS_OUTPUT_DIR, settings.TIFF_FORMAT_CUM.format(hours))
        utils.write_geotiff(accum_rainfall, tif_abspath)
        # Alerts evaluations
        utils.compare_precip(accum_rainfall, hours)