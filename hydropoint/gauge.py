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

    # multi-day totals are treated as gaps
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
    # gauge rain where available, otherwise SILO
    out = daily.merge(gauge, on='Date', how='left')
    out[SILO_RAIN] = out[rain_column]
    use_gauge = out[GAUGE].notna()
    out[rain_column] = out[GAUGE].where(use_gauge, out[SILO_RAIN])
    out[SOURCE] = use_gauge.map({True: 'Gauge', False: 'SILO'})
    return out


# %% observed temperature (BoM IDCJAC0010 Tmax, IDCJAC0011 Tmin)

# variable: (words in the BoM column name, observed column, SILO column, source column)
TEMPERATURE = {
    'Tmax': (('maximum', 'temperature'), 'Maximum temperature, observed (degC)',
             'Maximum temperature, SILO (degC)', 'Maximum temperature source'),
    'Tmin': (('minimum', 'temperature'), 'Minimum temperature, observed (degC)',
             'Minimum temperature, SILO (degC)', 'Minimum temperature source'),
}
OBSERVED, NOT_QC, SILO_FILL = 'Observed', 'Observed, not QC', 'SILO'


def temperature_kind(table):
    # 'Tmax' or 'Tmin' for a BoM daily temperature download, otherwise None
    cols = [str(c).strip().lower() for c in table.columns]
    if not all(c in cols for c in ('year', 'month', 'day')):
        return None
    for kind, (words, *_) in TEMPERATURE.items():
        column = _find(table.columns, *words)
        if column is not None and 'accumulation' not in str(column).lower():
            return kind
    return None


def bom_temperature_to_daily(table, kind):
    # observed value and whether BoM has quality controlled it (Quality = Y)
    words, observed, _, _ = TEMPERATURE[kind]
    lower = {str(c).strip().lower(): c for c in table.columns}
    dates = pd.to_datetime(dict(year=table[lower['year']], month=table[lower['month']],
                                day=table[lower['day']]), errors='coerce')
    value_col = next(c for c in table.columns
                     if all(w in str(c).lower() for w in words) and 'accumulation' not in str(c).lower())
    out = pd.DataFrame({'Date': dates, observed: pd.to_numeric(table[value_col], errors='coerce')})
    quality_col = _find(table.columns, 'quality')
    out['qc'] = (table[quality_col].astype(str).str.strip().str.upper() == 'Y') if quality_col is not None else True

    # extremes over more than one day are treated as gaps
    days_col = _find(table.columns, 'accumulation')
    if days_col is not None:
        days = pd.to_numeric(table[days_col], errors='coerce')
        out.loc[days > 1, observed] = float('nan')
    out = out.dropna(subset=['Date', observed])
    return out.groupby('Date', as_index=False).first().sort_values('Date').reset_index(drop=True)


def merge_temperature(daily, observed_daily, kind, column):
    # observed temperature where available, otherwise SILO
    _, observed, silo_col, source = TEMPERATURE[kind]
    out = daily.merge(observed_daily, on='Date', how='left')
    out[silo_col] = out[column]
    use = out[observed].notna()
    out[column] = out[observed].where(use, out[silo_col])
    out[source] = SILO_FILL
    out.loc[use & out['qc'].eq(True), source] = OBSERVED
    out.loc[use & ~out['qc'].eq(True), source] = NOT_QC
    return out.drop(columns='qc')


def group_with(frame, column, extras):
    # put the extra columns straight after the column they describe
    extras = [c for c in extras if c in frame.columns]
    order = [c for c in frame.columns if c not in extras]
    i = order.index(column) + 1
    return frame[order[:i] + extras + order[i:]]
