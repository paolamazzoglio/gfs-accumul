ADDRESSES = {
    'grib': {
        'url': 'ftp.ncep.noaa.gov',
        'folder': 'pub/data/nccf/com/gfs/prod',
    },
    'nomads': {
        'base_url': 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?'
    }}

GFS_DATA_DIR = '/path/to/directory/for/data/download'

GFS_OUTPUT_DIR = '/path/to/directory/for/output/data'

THRESHOLDS_DIR_ABSPATH = '/path/to/threshold/ini_config/file'

GFS_TYPE = 'nomads'

GFS_TYPE_PREFIX = 'gfs.t00z.pgrb2.0p25.f'

APCP_FORMAT = 'apcp_gfs_*.bin'

DATE_FORMAT = '%Y%m%d'

TIFF_FORMAT_CUM = 'gfs_apcp_accumulated_{:03d}h.tif'

TIFF_FORMAT_ALERTS = 'gfs_apcp_alerts_{:03d}h.tif'

UPDATE_FILE = 'update.txt'

DATETIME_FORMAT = '%Y-%m-%dT%H:%M%z'

aggregation_intervals = [12, 24, 48, 72, 96]

apcp_shape = (721, 1440)




