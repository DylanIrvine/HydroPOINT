# runs the calculations in order and builds the settings table

import datetime as dt

import pandas as pd

from . import VERSION, gauge as gauge_mod, metrics
from .metrics import MONTHS, WY
from .silo import RAIN, RH_TMAX, TMAX, TMIN


def run(silo_daily, settings, gauge=None, tmax_obs=None, tmin_obs=None):
    s = dict(metrics.DEFAULTS, **settings)
    daily = silo_daily.copy()
    if gauge is not None:
        daily = gauge_mod.merge_gauge(daily, gauge, RAIN)
        daily = gauge_mod.group_with(daily, RAIN, [gauge_mod.GAUGE, gauge_mod.SILO_RAIN, gauge_mod.SOURCE])
    for kind, column, observed in [('Tmax', TMAX, tmax_obs), ('Tmin', TMIN, tmin_obs)]:
        if observed is not None:
            daily = gauge_mod.merge_temperature(daily, observed, kind, column)
            daily = gauge_mod.group_with(daily, column, list(gauge_mod.TEMPERATURE[kind][1:]))

    daily, mean_daily_rain = metrics.add_daily(daily, s)
    monthly = metrics.make_monthly(daily, s)
    annual, ref_means, wet_months = metrics.make_annual(daily, monthly, s)

    inc = annual['Included'] == 'Yes'
    s['_ref_years'] = [y for y in metrics.reference_years(annual[WY], s) if y in set(annual.loc[inc, WY])]
    return dict(daily=daily, monthly=monthly, annual=annual, settings=s, ref_means=ref_means,
                wet_months=wet_months, mean_daily_rain=mean_daily_rain,
                climatology=metrics.monthly_climatology(monthly, s),
                monthly_ranges=metrics.monthly_ranges(monthly, s))


def settings_table(result, meta):
    # rows for the Settings sheet
    s = result['settings']
    annual = result['annual']
    daily = result['daily']
    start = s['wy_start_month']
    ref = s['_ref_years']
    rows = [
        ('App', f"HydroPOINT version {VERSION}"),
        ('Run date', dt.date.today().isoformat()),
        ('Data source', 'SILO Data Drill, Queensland Government (https://www.longpaddock.qld.gov.au/silo/)'),
        ('Latitude entered', meta['latitude']),
        ('Longitude entered', meta['longitude']),
        ('SILO grid cell (lat, lon)', f"{meta['cell_lat']:.2f}, {meta['cell_lon']:.2f}"),
        ('Start date entered', str(meta['start'])),
        ('Years of padding before the start', meta['pad_years']),
        ('First day of data', daily['Date'].min().date().isoformat()),
        ('Last day of data', daily['Date'].max().date().isoformat()),
        ('First month of the water year', MONTHS[start - 1]),
        ('Water year naming', 'By the calendar year it starts in'),
        ('Minimum days for a water year to be included', s['min_days']),
        ('Water years in the record', len(annual)),
        ('Water years included', int((annual['Included'] == 'Yes').sum())),
        ('Reference period', 'Entire record' if s['ref_mode'] == 'entire'
         else f"Water years {s['ref_start']} to {s['ref_end']}"),
        ('Reference water years used', f"{min(ref)} to {max(ref)} ({len(ref)} years)"),
        ('Reference mean annual rain (mm)', round(result['ref_means'][RAIN], 1)),
        ('Mean daily rain, entire record (mm)', round(result['mean_daily_rain'], 4)),
        ('Rain day threshold (mm)', s['rain_day_mm']),
        ('Rain spell length (days)', s['rain_spell_days']),
        ('Tmin threshold (degC)', s['tmin_threshold']),
        ('Tmin spell length (days)', s['tmin_spell_days']),
        ('Tmax threshold (degC)', s['tmax_threshold']),
        ('Tmax spell length (days)', s['tmax_spell_days']),
        ('Wet season months', ', '.join(MONTHS[m - 1] for m in result['wet_months'])),
    ]
    if meta.get('gauge_name'):
        source = daily['Rain source'].value_counts()
        rows += [
            ('Gauge file', meta['gauge_name']),
            ('Days of rain from the gauge', int(source.get('Gauge', 0))),
            ('Days of rain filled from SILO', int(source.get('SILO', 0))),
            ('Gauge rule', 'Gauge totals measured over more than one day are treated as gaps and filled from SILO'),
        ]
    else:
        rows.append(('Gauge file', 'None. All rain is from SILO'))
    for kind, column in [('Tmax', TMAX), ('Tmin', TMIN)]:
        source_col = gauge_mod.TEMPERATURE[kind][3]
        name = meta.get(f'{kind.lower()}_name')
        if name and source_col in daily:
            source = daily[source_col].value_counts()
            rows += [
                (f'Observed {kind} file', name),
                (f'Days of {kind} observed and quality controlled', int(source.get(gauge_mod.OBSERVED, 0))),
                (f'Days of {kind} observed, not yet quality controlled', int(source.get(gauge_mod.NOT_QC, 0))),
                (f'Days of {kind} filled from SILO', int(source.get(gauge_mod.SILO_FILL, 0))),
            ]
        else:
            rows.append((f'Observed {kind} file', f'None. All {kind} is from SILO'))
    if any(meta.get(k) for k in ('tmax_name', 'tmin_name')):
        rows.append(('Observed temperature rule',
                     'Observed values are used where they exist, including those BoM has not yet quality '
                     'controlled (Quality N). Values over more than one day are treated as gaps and filled '
                     'from SILO. SILO PET is not recalculated, so it still uses the SILO temperatures'))
    if metrics.WET_BULB in daily:
        blank = int((daily[metrics.WET_BULB].isna() & daily[RH_TMAX].notna() & daily[TMAX].notna()).sum())
        rows.append(('Days with wet-bulb left blank (outside the Stull range)', blank))
    rows += [
        ('', ''),
        ('Definitions', ''),
        ('Rain day', 'Rain at or above the rain day threshold (any rain above zero if the threshold is 0)'),
        ('Excess water', 'Daily rain less daily PET, set to zero where negative, then summed'),
        ('Rain n-day total', 'Sum of rain over the n days ending on that date'),
        ('Rain residual mass', 'Running sum of rain less the mean rain of the entire record (daily, monthly or annual). '
                               'The reference period is not used'),
        ('Spells', 'Runs of consecutive days. Annual values count runs inside each water year only'),
        ('Spells of n+ days', 'Number of separate runs at least n days long'),
        ('PCI', 'Precipitation concentration index (Oliver 1980): 100 x sum of squared monthly rain / annual rain squared'),
        ('Seasonality index', 'Walsh and Lawler (1981): sum of |monthly rain - annual rain / 12| / annual rain'),
        ('Wet season share', 'Share of the water year rain that fell in the wet season months. These are the six '
                             'consecutive months with the most rain on average over the reference period'),
        ('Anomaly', 'Value less the mean over the included water years of the reference period'),
        ('Wet-bulb temperature at Tmax', 'Stull (2011) estimate from daily Tmax and the SILO relative humidity at '
                                         'Tmax: Tw = T atan[0.151977 (RH + 8.313659)^0.5] + atan(T + RH) - '
                                         'atan(RH - 1.676331) + 0.00391838 RH^1.5 atan(0.023101 RH) - 4.686035. '
                                         'Fitted for sea level pressure, RH of 5 to 99% and T of -20 to 50 degC. '
                                         'Days outside that range are left blank. SILO RH at Tmax uses the 9 am '
                                         'vapour pressure, so it assumes the moisture at 9 am holds at the time '
                                         'of Tmax. Where observed Tmax is used, the RH is rescaled to it: '
                                         'RH x es(SILO Tmax) / es(Tmax used), with es from FAO56 equation 11, '
                                         'capped at 100%. Monthly and annual values are the mean and maximum '
                                         'of the daily values'),
        ('Included', 'Water years with fewer days than the minimum are flagged No. Their totals are still '
                     'listed, but indices, anomalies and the annual residual mass are left blank'),
    ]
    return pd.DataFrame(rows, columns=['Setting', 'Value']).astype({'Value': str})
