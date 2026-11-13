# SILO Data Drill download for one grid cell. Same request and parser as HydroSILO

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from io import StringIO

import numpy as np
import pandas as pd

SILO_API_URL = 'https://www.longpaddock.qld.gov.au/cgi-bin/silo/DataDrillDataset.php'
SILO_FIRST_DAY = pd.Timestamp('1889-01-01')
GRID = 0.05
# rough extent of the SILO grid
LAT_RANGE = (-44.0, -10.0)
LON_RANGE = (112.0, 154.0)

RAIN = 'Rain (mm)'
PET_FAO = 'FAO56 PET (mm)'
PET_MWET = 'Morton wet-environment areal PET (mm)'
TMAX = 'Maximum temperature (degC)'
TMIN = 'Minimum temperature (degC)'

# every variable in the SILO 'alldata' format: short name, column name used here,
# and how it is collated to months and years. The source (quality) columns such
# as Smx and Srn are left out. The first five are needed; the rest are kept if present
VARIABLES = [
    ('Rain', RAIN, 'sum'),
    ('FAO56', PET_FAO, 'sum'),
    ('Mwet', PET_MWET, 'sum'),
    ('T.Max', TMAX, 'mean'),
    ('T.Min', TMIN, 'mean'),
    ('Evap', 'Pan evaporation (mm)', 'sum'),
    ('Span', 'Synthetic pan evaporation (mm)', 'sum'),
    ('EvSp', 'Pan evaporation, synthetic before 1970 (mm)', 'sum'),
    ('Mlake', 'Morton shallow lake evaporation (mm)', 'sum'),
    ('Mpot', 'Morton potential evapotranspiration (mm)', 'sum'),
    ('Mact', 'Morton actual evapotranspiration (mm)', 'sum'),
    ('Radn', 'Solar radiation (MJ/m2)', 'mean'),
    ('VP', 'Vapour pressure (hPa)', 'mean'),
    ('RHmaxT', 'Relative humidity at Tmax (%)', 'mean'),
    ('RHminT', 'Relative humidity at Tmin (%)', 'mean'),
    ('MSLPres', 'Sea level pressure (hPa)', 'mean'),
    ('MSLP', 'Sea level pressure (hPa)', 'mean'),
]
REQUIRED = ('Rain', 'FAO56', 'Mwet', 'T.Max', 'T.Min')
# column name -> 'sum' or 'mean'
COLLATE = {name: how for _, name, how in VARIABLES}
CORE = [RAIN, PET_FAO, PET_MWET, TMAX, TMIN]


def other_variables(frame):
    # the SILO variables in a table beyond the five core ones
    return [c for c in frame.columns if c in COLLATE and c not in CORE]


def snap_to_grid(latitude, longitude):
    # centre of the 0.05 degree cell the point falls in
    lat = round(np.round(latitude / GRID) * GRID, 2)
    lon = round(np.round(longitude / GRID) * GRID, 2)
    return float(lat), float(lon)


def padded_start(start, pad_years):
    # move the start back by pad_years, but not before the SILO record begins
    start = pd.Timestamp(start)
    early = start - pd.DateOffset(years=int(pad_years))
    return max(early, SILO_FIRST_DAY)


def parse_silo_alldata(data):
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()

    header = next((i for i, line in enumerate(lines)
                   if re.match(r'^\s*Date\s+Day\s+Date2\b', line)), None)
    if header is None or header + 2 >= len(lines):
        preview = '\n'.join(lines[:20])
        raise ValueError(f'SILO returned an unrecognised response:\n{preview}')

    names = re.split(r'\s+', lines[header].strip())
    body = '\n'.join(lines[header + 2:])
    raw = pd.read_csv(StringIO(body), sep=r'\s+', names=names, header=None, engine='python')

    numeric_date = pd.to_numeric(raw['Date'], errors='coerce')
    raw = raw.loc[numeric_date.notna()].copy()
    raw['Date'] = pd.to_datetime(numeric_date.dropna().astype('int64').astype(str), format='%Y%m%d')

    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"SILO response is missing columns: {', '.join(missing)}")

    out = pd.DataFrame({'Date': raw['Date']})
    for source, name, _ in VARIABLES:
        if source in raw.columns and name not in out.columns:
            out[name] = pd.to_numeric(raw[source], errors='coerce')
    return out.reset_index(drop=True)


def download_silo_point(latitude, longitude, start, end, email, timeout=180, max_attempts=3):
    # start and end are yyyymmdd strings. The email is the SILO username
    parameters = {
        'format': 'alldata',
        'lat': f'{latitude:.2f}',
        'lon': f'{longitude:.2f}',
        'start': start,
        'finish': end,
        'username': email,
        'password': 'apirequest',
        'comment': 'point',
    }
    url = SILO_API_URL + '?' + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, headers={'User-Agent': 'HydroPOINT-app'})

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return parse_silo_alldata(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            if attempt == max_attempts:
                raise RuntimeError(
                    f'SILO download failed at {latitude:.2f}, {longitude:.2f} '
                    f'after {attempt} attempts: {error}') from error
            time.sleep(2 ** (attempt - 1))
