# read a daily rain gauge file and merge it with SILO rain

import pandas as pd

GAUGE = 'Gauge rain (mm)'
SILO_RAIN = 'SILO rain (mm)'
SOURCE = 'Rain source'


def _find(columns, *words):
    # first column whose lower-case name contains all the words
    for column in columns:
        name = str(column).lower()
        if all(word in name for word in words):
            return column
    return None


def is_bom_format(table):
    cols = [str(c).strip().lower() for c in table.columns]
    return all(c in cols for c in ('year', 'month', 'day')) and _find(table.columns, 'rainfall') is not None


def read_table(buffer):
    return pd.read_csv(buffer, skipinitialspace=True)


def bom_to_daily(table):
    # BoM daily rainfall download (IDCJAC0009): Year, Month, Day, rainfall, period, quality
    lower = {str(c).strip().lower(): c for c in table.columns}
    dates = pd.to_datetime(dict(year=table[lower['year']], month=table[lower['month']],
                                day=table[lower['day']]), errors='coerce')
    rain = pd.to_numeric(table[_find(table.columns, 'rainfall')], errors='coerce')
    out = pd.DataFrame({'Date': dates, GAUGE: rain})

    # a total measured over more than one day cannot be placed on a single day,
    # so it is treated as a gap and filled from SILO
    period_col = _find(table.columns, 'period')
    if period_col is not None:
        period = pd.to_numeric(table[period_col], errors='coerce')
        out.loc[period > 1, GAUGE] = float('nan')
    return _tidy(out)


def generic_to_daily(table, date_column, rain_column, dayfirst=True):
    dates = pd.to_datetime(table[date_column], errors='coerce', dayfirst=dayfirst)
    rain = pd.to_numeric(table[rain_column], errors='coerce')
    return _tidy(pd.DataFrame({'Date': dates.dt.normalize(), GAUGE: rain}))


def _tidy(out):
    out = out.dropna(subset=['Date'])
    out.loc[out[GAUGE] < 0, GAUGE] = float('nan')
    return out.groupby('Date', as_index=False)[GAUGE].first().sort_values('Date').reset_index(drop=True)


def merge_gauge(daily, gauge, rain_column):
    # gauge rain where it exists, SILO rain in the gaps. The SILO series is kept alongside
    out = daily.merge(gauge, on='Date', how='left')
    out[SILO_RAIN] = out[rain_column]
    use_gauge = out[GAUGE].notna()
    out[rain_column] = out[GAUGE].where(use_gauge, out[SILO_RAIN])
    out[SOURCE] = use_gauge.map({True: 'Gauge', False: 'SILO'})
    return out
