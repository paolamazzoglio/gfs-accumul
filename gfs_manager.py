import configparser
import datetime
import numpy as np
import os
from builtins import str
import settings
import utils
from operator import attrgetter



class GFSManager():

    # Management of GFS data in grib format
    def __init__(self, abspath):
        self.abspath = abspath
        self.dirname = os.path.dirname(abspath)
        self.basename = os.path.basename(abspath)
        self.bin_basename = None

    def APCP2bin(self):
        # Conversion and saving in binary format.
        self.bin_basename = 'apcp_' + self.basename + '.bin'
        try:
            bash_command = 'wgrib2 %s -bin %s -match "1:" -order we:ns -no_header' \
                         % (os.path.join(self.dirname, self.basename), os.path.join(self.dirname, self.bin_basename))
            os.system(bash_command)
            # Cancellation of the downloaded file
            os.remove(os.path.join(self.dirname, self.basename))
        except:
            pass



class APCPManager:

    SDTFORMAT = '%Y%m%d'

    def __init__(self, abspath):
        self.abspath = abspath
        self.dirname = os.path.dirname(abspath)
        self.basename = os.path.basename(abspath)
        self.bin_basename = None
        self.model_exc_dt = None
        self.end_dt = None
        self.forecast_time = None
        self._precip = None
        self._set_datetimes()

    @property
    def precip(self):
        if self._precip is None:
            try:
                # Reading and reshaping from array to matrix
                matrix_temp = np.fromfile(os.path.join(self.dirname, self.basename), np.float32).reshape(settings.apcp_shape[0], settings.apcp_shape[1])
                # Ignore the last row
                matrix_temp = matrix_temp[1:,]
                # Reverse from 0/360 to -180/+180
                right_matrix = matrix_temp[:, 720:]
                left_matrix = matrix_temp[:, :720]
                reversed_matrix = np.hstack((right_matrix, left_matrix))
                del left_matrix
                del right_matrix
                del matrix_temp
                self._precip = reversed_matrix
            except OSError:
                print('Cannot read GFS file:', self.basename)
        return self._precip

    def _set_datetimes(self):
        datetimeinfo = self.basename.split('_')[3]
        dateshift = int(datetimeinfo.split('.')[0])
        dateshift = datetime.timedelta(hours=dateshift)
        self.forecast_time = dateshift
        sdate = self.basename.split('_')[2]
        sdate = sdate[0:-2]
        naive_start_dt = datetime.datetime.strptime(sdate, self.SDTFORMAT)
        naive_end_dt = naive_start_dt + dateshift
        self.model_exc_dt = naive_start_dt.replace(tzinfo=datetime.timezone.utc)
        self.end_dt = naive_end_dt.replace(tzinfo=datetime.timezone.utc)



class FakeAPCPManager:
    def __init__(self, forecast_time):
        self.precip = np.zeros([settings.apcp_shape[0]-1, settings.apcp_shape[1]])
        self.forecast_time = forecast_time



class GFS_APCP_TimeSerie:

    # Definition of the temporal resolution of every GFS file
    time_res = datetime.timedelta(hours=6)

    def __init__(self, start_dt, agg_interval, datadir):
        if not isinstance(start_dt, datetime.datetime):
            raise ValueError('start_dt must be of type datetime!')
        self.start_dt = start_dt

        if not isinstance(agg_interval, int):
            raise ValueError('agg_interval, number of hours, must be of type integer!')
        self.agg_interval = agg_interval
        self.td_agg_interval = datetime.timedelta(hours=agg_interval)

        if not isinstance(datadir, str):
            raise ValueError('datadir must be of type string!')
        self.datadir = datadir

        self.end_dt = self.start_dt + self.td_agg_interval
        # Evaluation of the expected number of files
        self.exp_nmeas = self.td_agg_interval // self.time_res
        self.measurements = []
        self.dt_index = None
        self._serie = None
        self._accumul = None

    @property
    def serie(self):
        if self._serie is None:
            self._build_serie()
        return self._serie

    @property
    def accumul(self):
        if self._accumul is None:
            self._accumul = np.int16(np.sum(self.serie, axis=0, keepdims=False))
        return self._accumul

    def _build_serie(self):
        for meas_fname in utils.get_apcps():
            meas_abspath = os.path.join(self.datadir, meas_fname)
            gfs_meas = APCPManager(meas_abspath)
            if gfs_meas.model_exc_dt == self.start_dt and gfs_meas.forecast_time <= self.td_agg_interval:
                self.measurements.append(gfs_meas)
            self.measurements.sort(key=attrgetter('forecast_time'))
            if len(self.measurements) != self.exp_nmeas:
                print("Missing measurements in the serie!")
                self._fix_serie()
        self.dt_index = tuple(measure.forecast_time for measure in self.measurements)
        self._serie = np.array([measure.precip for measure in self.measurements])

    def _fix_serie(self):
        restart = True
        while restart:
            restart = False
            for i, meas in enumerate(self.measurements.copy()):
                if meas.forecast_time != (i + 1) * self.time_res:
                    print('Using zeros to replace measure with forecast time equal to ' + str((self.time_res.total_seconds() / 3600) * (i + 1)) + ' hours.')
                    self.measurements.insert(i, FakeAPCPManager((i + 1) * self.time_res))
                    restart = True
                    break

    def save_accumul(self):
        out_abspath = os.path.join(settings.GFS_OUTPUT_DIR, settings.TIFF_FORMAT_CUM.format(self.agg_interval))
        # Rotation
        accumul_rainfall = np.rot90(np.rot90(np.rot90(self.accumul)))
        # Saving
        utils.write_geotiff(accumul_rainfall, out_abspath)

    def latest_subserie(self, duration, agg_interval):
        self.agg_interval = agg_interval

        if self._serie is None:
            raise ValueError('No need to create a subserie from a non-built serie.')

        if duration >= self.td_agg_interval:
            raise ValueError('Required duration of subserie is greater than original serie.')

        subserie = GFS_APCP_TimeSerie(self.start_dt, self.agg_interval, self.datadir)
        n_throw = self.exp_nmeas - subserie.exp_nmeas
        subserie.measurements = self.measurements[n_throw:]

        subserie.dt_index = self.dt_index[:-n_throw]
        subserie._serie = self.serie[:-n_throw]
        return subserie



class GridThreshold:
    SECTION = 'Grid Thresholds'

    def __init__(self, hours):
        if not isinstance(hours, int):
            raise ValueError('Duration must be expressed in hours, integer value is expected!')
        self.hours = hours
        self._grid = None
        config = configparser.ConfigParser()
        config.read(settings.THRESHOLDS_DIR_ABSPATH)
        self.ref = '{:03d}h'.format(hours)
        self.grid_fname = config[self.SECTION][self.ref]
        self.grid_apath = os.path.join(os.path.dirname(settings.THRESHOLDS_DIR_ABSPATH), self.grid_fname)
        del config

    @property
    def grid(self):
        if self._grid is None:
            grid_toflip = utils.tiff2array(self.grid_apath).T
            self._grid = np.fliplr(grid_toflip)
            return self._grid



class AlertDetector:
    tif_basename = settings.TIFF_FORMAT_ALERTS

    def __init__(self, accum_rainfall, hours):
        self.accum_rainfall = accum_rainfall
        self.hours = hours

        try:
            self.threshold_obj = GridThreshold(self.hours)
        except:
            print('Grid threshold not available for {:3d} hours duration'.format(self.hours))
            self.total_alerts = None

    def detect_alerts(self):
        threshold_temp = self.threshold_obj.grid
        threshold_temp = np.rot90(threshold_temp)

        total_alerts_temp = (self.accum_rainfall > threshold_temp).astype(np.int16)
        self.total_alerts = np.rot90(np.rot90(total_alerts_temp))
        return self.total_alerts

    def get_masked_alerts(self):
        alerts = self.detect_alerts()
        mask = self.get_mask()
        alerts_masked = alerts * np.flipud(np.rot90(np.rot90(np.rot90(mask))))
        alerts_masked = np.rot90(alerts_masked)
        return alerts_masked

    def save_masked_alerts(self, out_dir):
        tif_basename = settings.TIFF_FORMAT_ALERTS.format(self.hours)
        tif_abspath = os.path.join(out_dir, tif_basename)
        utils.write_geotiff(self.get_masked_alerts(), tif_abspath)

    def get_mask(self):
        config = configparser.ConfigParser()
        config.read(settings.THRESHOLDS_DIR_ABSPATH)
        mask_filename = config['Files']['mask']
        mask_dirname = os.path.dirname(settings.THRESHOLDS_DIR_ABSPATH)
        mask_abspath = os.path.join(mask_dirname, mask_filename)
        gpm_mask = utils.tiff2array(mask_abspath)
        return (gpm_mask.T)