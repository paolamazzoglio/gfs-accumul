import configparser
import numpy as np
import os
import settings
import utils



class GFSManager():
    def __init__(self, abspath):
        self.abspath = abspath
        self.dirname = os.path.dirname(abspath)
        self.basename = os.path.basename(abspath)
        self.bin_basename = None

    def APCP2bin(self):
        # Conversion and saving in binary format.
        self.bin_basename = 'apcp_' + self.basename + '.bin'
        try:
            bash_command = 'wgrib2 %s -bin %s -match "1:" -order we:ns -no_header' % (os.path.join(self.dirname, self.basename), os.path.join(self.dirname, self.bin_basename))
            os.system(bash_command)
            # Cancellation of the downloaded file
            os.remove(os.path.join(self.dirname, self.basename))
        except:
            pass



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
        self.total_alerts = (self.accum_rainfall > self.threshold_obj.grid).astype(np.int16)
        return self.total_alerts

    def get_masked_alerts(self):
        alerts = self.detect_alerts()
        mask = self.get_mask()
        alerts_masked = alerts * np.rot90(np.rot90(mask))
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
        global_mask = utils.tiff2array(mask_abspath)
        gpm_mask = np.fliplr(global_mask)
        return (gpm_mask.T)