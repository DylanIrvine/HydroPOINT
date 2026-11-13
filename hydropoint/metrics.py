# daily, monthly and water-year calculations

import numpy as np
import pandas as pd

from .silo import RAIN, PET_FAO, PET_MWET, TMAX, TMIN

WY = 'Water year'
EXCESS_FAO = 'Excess water FAO56 (mm)'
EXCESS_MWET = 'Excess water Morton (mm)'
RAIN_WINDOWS = (3, 7, 14, 30)
RESIDUAL = 'Rain residual mass (mm)'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

DEFAULTS = dict(
    wy_start_month=9,       # first month of the water year
    rain_day_mm=1.0,        # a rain day has at least this much rain
    rain_spell_days=3,
    tmin_threshold=5.0,
    tmin_spell_days=3,
    tmax_threshold=35.0,
    tmax_spell_days=3,
    min_days=350,           # days of data needed for a water year to be included
    ref_mode='entire',      # 'entire' or 'period'
    ref_start=None,         # first and last water year of the reference period
    ref_end=None,
)


def water_year(dates, start_month):
    # named by the calendar year it starts in: Sep 2000 to Aug 2001 is 2000
    dates = pd.DatetimeIndex(dates)
    return np.where(dates.month >= start_month, dates.year, dates.year - 1)


def day_of_water_year(dates, start_month):
    dates = pd.DatetimeIndex(dates)
    starts = pd.to_datetime(dict(year=water_year(dates, start_month), month=start_month, day=1))
    return (dates - pd.DatetimeIndex(starts)).days


def is_rain_day(rain, threshold):
    return rain >= threshold if threshold > 0 else rain > 0


def running_count(flag):
    # number of days in a row, up to and including each day, that the flag is true
    flag = flag.fillna(False).astype(int)
    return flag.groupby((flag == 0).cumsum()).cumsum()


def spell_stats(flag, min_length):
    # longest run of true values, and the number of runs at least min_length long
    values = np.asarray(flag, dtype=bool).astype(int)
    edges = np.diff(np.concatenate(([0], values, [0])))
    lengths = np.where(edges == -1)[0] - np.where(edges == 1)[0]
    if len(lengths) == 0:
        return 0, 0
    return int(lengths.max()), int((lengths >= min_length).sum())


def pci(monthly_rain):
    # precipitation concentration index (Oliver 1980). 8.3 is perfectly even
    total = monthly_rain.sum()
    return 100 * (monthly_rain ** 2).sum() / total ** 2 if total > 0 else np.nan


def seasonality_index(monthly_rain):
    # Walsh and Lawler (1981). 0 is perfectly even, 1.83 is all rain in one month
    total = monthly_rain.sum()
    return (monthly_rain - total / 12).abs().sum() / total if total > 0 else np.nan


def reference_years(years, s):
    # water years that make up the reference period
    if s['ref_mode'] == 'period':
        return [y for y in years if s['ref_start'] <= y <= s['ref_end']]
    return list(years)


# %% daily

def add_daily(daily, s):
    out = daily.copy()
    out.insert(1, WY, water_year(out['Date'], s['wy_start_month']))

    out[EXCESS_FAO] = (out[RAIN] - out[PET_FAO]).clip(lower=0)
    out[EXCESS_MWET] = (out[RAIN] - out[PET_MWET]).clip(lower=0)

    for n in RAIN_WINDOWS:
        out[f'Rain {n}-day total (mm)'] = out[RAIN].rolling(n, min_periods=n).sum()

    # residual mass: running sum of the departure from the mean daily rain
    in_ref = out[WY].isin(reference_years(out[WY].unique(), s))
    mean_rain = out.loc[in_ref, RAIN].mean()
    out[RESIDUAL] = (out[RAIN] - mean_rain).fillna(0).cumsum()

    out['Rain day'] = is_rain_day(out[RAIN], s['rain_day_mm']).astype(int)
    out['Consecutive rain days'] = running_count(out['Rain day'] == 1)
    out['Consecutive dry days'] = running_count(out['Rain day'] == 0)
    out[f"Consecutive days Tmin below {s['tmin_threshold']:g}"] = running_count(out[TMIN] < s['tmin_threshold'])
    out[f"Consecutive days Tmax above {s['tmax_threshold']:g}"] = running_count(out[TMAX] > s['tmax_threshold'])
    return out, mean_rain


# %% monthly

def make_monthly(daily, s):
    d = daily.assign(Year=daily['Date'].dt.year, Month=daily['Date'].dt.month)
    g = d.groupby(['Year', 'Month'])
    out = pd.DataFrame({
        'Days of data': g[RAIN].count(),
        RAIN: g[RAIN].sum(),
        'Rain days': g['Rain day'].sum(),
        'Max 1-day rain (mm)': g[RAIN].max(),
        PET_FAO: g[PET_FAO].sum(),
        PET_MWET: g[PET_MWET].sum(),
        EXCESS_FAO: g[EXCESS_FAO].sum(),
        EXCESS_MWET: g[EXCESS_MWET].sum(),
        'Mean Tmax (degC)': g[TMAX].mean(),
        'Mean Tmin (degC)': g[TMIN].mean(),
    }).reset_index()

    first = pd.to_datetime(dict(year=out['Year'], month=out['Month'], day=1))
    out.insert(2, WY, water_year(first, s['wy_start_month']))
    out['Complete month'] = np.where(out['Days of data'] == first.dt.days_in_month, 'Yes', 'No')

    # residual mass two ways: against the mean of all months, and against the mean
    # for each calendar month (which takes the seasonal cycle out)
    ref = (out['Complete month'] == 'Yes') & out[WY].isin(reference_years(out[WY].unique(), s))
    complete = out['Complete month'] == 'Yes'
    overall = out.loc[ref, RAIN].mean()
    by_month = out.loc[ref].groupby('Month')[RAIN].mean()
    out['Rain residual mass, all-month mean (mm)'] = (out[RAIN] - overall).where(complete, 0).cumsum()
    out['Rain residual mass, calendar-month mean (mm)'] = (
        (out[RAIN] - out['Month'].map(by_month)).where(complete, 0).fillna(0).cumsum())
    return out


def monthly_climatology(monthly, s):
    # mean for each calendar month over the reference period, in water-year order
    ref = (monthly['Complete month'] == 'Yes') & monthly[WY].isin(reference_years(monthly[WY].unique(), s))
    clim = monthly.loc[ref].groupby('Month')[[RAIN, PET_FAO, PET_MWET]].mean()
    order = [(s['wy_start_month'] - 1 + i) % 12 + 1 for i in range(12)]
    return clim.reindex(order)


def wet_season_months(monthly, s):
    # the six consecutive calendar months with the most rain on average
    clim = monthly_climatology(monthly, s)[RAIN].reindex(range(1, 13)).fillna(0).to_numpy()
    totals = [sum(clim[(start + i) % 12] for i in range(6)) for start in range(12)]
    start = int(np.argmax(totals))
    return [(start + i) % 12 + 1 for i in range(6)]


# %% annual (water year)

def make_annual(daily, monthly, s):
    wet_months = wet_season_months(monthly, s)
    rows = []
    for wy, d in daily.groupby(WY):
        days = int(d[RAIN].count())
        included = days >= s['min_days']
        rain_day = d['Rain day'] == 1
        m = monthly.loc[monthly[WY] == wy, ['Month', RAIN]].set_index('Month')[RAIN]

        wet_run, wet_spells = spell_stats(rain_day, s['rain_spell_days'])
        dry_run, _ = spell_stats(~rain_day, 1)
        cold = (d[TMIN] < s['tmin_threshold']).fillna(False)
        hot = (d[TMAX] > s['tmax_threshold']).fillna(False)
        cold_run, cold_spells = spell_stats(cold, s['tmin_spell_days'])
        hot_run, hot_spells = spell_stats(hot, s['tmax_spell_days'])

        row = {
            WY: int(wy),
            'Start date': d['Date'].min(),
            'End date': d['Date'].max(),
            'Days of data': days,
            'Included': 'Yes' if included else 'No',
            RAIN: d[RAIN].sum(),
            'Rain days': int(rain_day.sum()),
            'Max consecutive rain days': wet_run,
            f"Rain spells of {s['rain_spell_days']}+ days": wet_spells,
            'Max consecutive dry days': dry_run,
            'Max 1-day rain (mm)': d[RAIN].max(),
        }
        for n in RAIN_WINDOWS:
            # windows are kept inside the water year
            row[f'Max {n}-day rain (mm)'] = d[RAIN].rolling(n, min_periods=n).sum().max()
        row.update({
            'PCI': pci(m) if included else np.nan,
            'Seasonality index': seasonality_index(m) if included else np.nan,
            'Wet season share of rain (%)': (100 * m.reindex(wet_months).sum() / m.sum()
                                             if included and m.sum() > 0 else np.nan),
            PET_FAO: d[PET_FAO].sum(),
            PET_MWET: d[PET_MWET].sum(),
            EXCESS_FAO: d[EXCESS_FAO].sum(),
            EXCESS_MWET: d[EXCESS_MWET].sum(),
            'Mean Tmax (degC)': d[TMAX].mean(),
            'Mean Tmin (degC)': d[TMIN].mean(),
            f"Days Tmin below {s['tmin_threshold']:g}": int(cold.sum()),
            f"Max consecutive days Tmin below {s['tmin_threshold']:g}": cold_run,
            f"Tmin spells of {s['tmin_spell_days']}+ days": cold_spells,
            f"Days Tmax above {s['tmax_threshold']:g}": int(hot.sum()),
            f"Max consecutive days Tmax above {s['tmax_threshold']:g}": hot_run,
            f"Tmax spells of {s['tmax_spell_days']}+ days": hot_spells,
        })
        rows.append(row)
    out = pd.DataFrame(rows)

    # anomalies against the reference period, using included years only
    inc = out['Included'] == 'Yes'
    ref = inc & out[WY].isin(reference_years(out[WY], s))
    if not ref.any():
        raise ValueError('No water year in the reference period has enough days of data. '
                         'Widen the reference period or lower the minimum number of days.')
    ref_means = {}
    for column, label in [(RAIN, 'Rain anomaly (mm)'), (PET_FAO, 'FAO56 PET anomaly (mm)'),
                          (PET_MWET, 'Morton PET anomaly (mm)'),
                          (EXCESS_FAO, 'Excess water FAO56 anomaly (mm)'),
                          (EXCESS_MWET, 'Excess water Morton anomaly (mm)'),
                          ('Mean Tmax (degC)', 'Tmax anomaly (degC)'),
                          ('Mean Tmin (degC)', 'Tmin anomaly (degC)')]:
        ref_means[column] = out.loc[ref, column].mean()
        out[label] = (out[column] - ref_means[column]).where(inc)
        if column == RAIN:
            out['Rain anomaly (%)'] = 100 * out[label] / ref_means[column]
    # residual mass over included years; years left out add nothing
    out['Rain residual mass (mm)'] = out['Rain anomaly (mm)'].fillna(0).cumsum().where(inc)
    return out, ref_means, wet_months
