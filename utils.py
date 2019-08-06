import datetime
import gfs_manager
import gdal
import glob
import numpy as np
import os
import osr
import settings
import urllib
from ftplib import FTP
from urllib import request



def connect(source):
    # This function connects to the remote ftp site
    addresses = settings.ADDRESSES
    ftp = FTP(addresses[source]['url'])
    ftp.login()
    ftp.cwd(addresses[source]['folder'])
    print('FTP connection established!')
    return ftp



def check_gfs_data(ftp):
    # Check folders list
    folders_list = ftp.nlst()
    filtered_folders_list = [foldername for foldername in folders_list if foldername.startswith('gfs.20')]
    filtered_folders_list.sort(reverse=True)
    ftp_folder = filtered_folders_list[0]
    # Check subfolders list
    subfolder_list = ftp.nlst(ftp_folder)
    subfolder_list.sort(reverse=True)
    # Check most recent subfolder
    for subfolder in subfolder_list:
        if subfolder.endswith(('00','12')):
            relevant_subfolder = subfolder
            return relevant_subfolder
        else:
            continue
    ftp.close()



def delete_last_update(relevant_subfolder):
    gfss = glob.glob(os.path.join(settings.GFS_DATA_DIR, settings.APCP_FORMAT))
    last_gfs_path = gfss[0]
    last_gfs = last_gfs_path[-18:-10] + '/' + str(last_gfs_path[-10:-8])
    if relevant_subfolder[4:] != last_gfs:
        print('New data available!')
        for old_file in gfss:
            try:
                os.remove(old_file)
            except OSError:
                print('Cannot remove old GFS file: ' + old_file)
    else:
        print('Latest available data already downloaded!')



def download_gfs_data(gfs_data_folder, relevant_subfolder):
    if settings.GFS_TYPE == 'nomads':
        for prev_time in range(6, 97, 6):
            try:
                # The code tries to download the data.
                if prev_time < 10:
                    prev_time = '00' + str(prev_time)
                else:
                    prev_time = '0' + str(prev_time)
                base_url = settings.ADDRESSES['nomads']['base_url']
                query_args = {'file': settings.GFS_TYPE_PREFIX[0:5] + relevant_subfolder[-2:] + settings.GFS_TYPE_PREFIX[7:] + prev_time, 'var_APCP': 'on', 'leftlon': '0', 'rightlon': '360', 'toplat': '90', 'bottomlat': '-90', 'dir': '/' + relevant_subfolder[0:-3] + "/" + relevant_subfolder[-2:]}
                encoded_args = urllib.parse.urlencode(query_args)
                url = base_url + encoded_args
                response = urllib.request.urlopen(url)
                data = response.read()
                filename = 'gfs_' + relevant_subfolder[4:-3] + relevant_subfolder[-2:] + '_' + prev_time
                with open(os.path.join(gfs_data_folder, filename),'wb') as f:
                    f.write(data)
            except:
                # If the file is corrupted, no action is performed.
                pass



def get_apcps(datadir):
    apcps = []
    for apcp_abspath in glob.iglob(os.path.join(datadir, settings.APCP_FORMAT)):
        apcps.append(os.path.basename(apcp_abspath))
    return apcps



def cumulate(datadir, hours):
    duration = datetime.timedelta(hours=hours)

    apcp_file_list = get_apcps(datadir)
    apcp_file_list.sort()

    first_date = apcp_file_list[0].split('_')[2]
    first_date = first_date[0:-2]
    first_date = datetime.datetime.strptime(first_date, settings.DATE_FORMAT)
    start_dt = first_date.replace(tzinfo=datetime.timezone.utc)
    end_dt = start_dt + duration

    num_file = 0

    for file in apcp_file_list:
        temp = int(file[-7:-4])
        time_shift = datetime.timedelta(hours=temp)
        end_dt_temp = start_dt + time_shift

        if end_dt_temp <= end_dt:
            num_file = num_file + 1
        else:
            pass

    apcp_file_list_cum = apcp_file_list[0:num_file]
    apcp = np.zeros(settings.apcp_shape)
    for apcp_file in apcp_file_list_cum:
        apcp += np.fromfile(os.path.join(settings.GFS_DATA_DIR, apcp_file), np.float32).reshape(settings.apcp_shape[0], settings.apcp_shape[1])
    apcp = apcp[0:-1,:]
    return apcp



def reverse_array(array):
    right_array = array[:, 720:]
    left_array = array[:, :720]
    reversed_array = np.hstack((right_array, left_array))
    reversed_array = np.rot90(np.rot90(np.rot90(reversed_array)))
    del left_array
    del right_array
    return reversed_array



def write_geotiff(array, out_abspath):
    gdal.AllRegister()
    driver = gdal.GetDriverByName('Gtiff')
    geotransform = (-180, 0.25, 0, -90, 0, 0.25)
    outDataset_options = ['COMPRESS=LZW']
    dtype = gdal.GDT_Float32
    outDataset = driver.Create(out_abspath, array.shape[0], array.shape[1], 1, dtype, outDataset_options)
    outDataset.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    outDataset.SetProjection(srs.ExportToWkt())
    outband = outDataset.GetRasterBand(1)
    outband.WriteArray(array.T)
    outband.GetStatistics(0, 1)
    outband = None
    outDataset = None



def tiff2array(tif_abspath):
    ds = gdal.Open(tif_abspath, gdal.GA_ReadOnly)
    array = ds.GetRasterBand(1).ReadAsArray()
    array = array.astype(int)
    return array



def compare_precip(accum_rainfall, hours):
    alert_detect = gfs_manager.AlertDetector(accum_rainfall, hours)
    alert_detect.save_masked_alerts(settings.GFS_OUTPUT_DIR)