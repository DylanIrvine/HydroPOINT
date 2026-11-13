# runs the calculations in order and builds the settings table

import datetime as dt

import pandas as pd

from . import VERSION, gauge as gauge_mod, metrics
from .metrics import MONTHS, WY
from .silo import RAIN


def run(silo_daily, settings, gauge=None):
    s = dict(metrics.DEFAULTS, **settings)
    daily = silo_daily.copy()
    if gauge is not None:
        daily = gauge_mod.merge_gauge(daily, gauge, RAIN)

    daily, mean_daily_rain = metrics.add_daily(daily, s)
    monthly = metrics.make_monthly(daily, s)
    annual, ref_means, wet_months = metrics.make_annual(daily, monthly, s)

    inc = annual['Included'] == 'Yes'
    s['_ref_years'] = [y for y in metrics.reference_years(annual[WY], s) if y in set(annual.loc[inc, WY])]
    return dict(daily=daily, monthly=monthly, annual=annual, settings=s, ref_means=ref_means,
                wet_months=wet_months, mean_daily_rain=mean_daily_rain,
                climatology=metrics.monthly_climatology(monthly, s))


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
        ('Reference mean daily rain (mm)', round(result['mean_daily_rain'], 4)),
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
    rows += [
        ('', ''),
        ('Definitions', ''),
        ('Rain day', 'Rain at or above the rain day threshold (any rain above zero if the threshold is 0)'),
        ('Excess water', 'Daily rain less daily PET, set to zero where negative, then summed'),
        ('Rain n-day total', 'Sum of rain over the n days ending on that date'),
        ('Rain residual mass', 'Running sum of rain less the reference mean rain (daily, monthly or annual)'),
        ('Spells', 'Runs of consecutive days. Annual values count runs inside each water year only'),
        ('Spells of n+ days', 'Number of separate runs at least n days long'),
        ('PCI', 'Precipitation concentration index (Oliver 1980): 100 x sum of squared monthly rain / annual rain squared'),
        ('Seasonality index', 'Walsh and Lawler (1981): sum of |monthly rain - annual rain / 12| / annual rain'),
        ('Wet season share', 'Share of the water year rain that fell in the wet season months. These are the six '
                             'consecutive months with the most rain on average over the reference period'),
        ('Anomaly', 'Value less the mean over the included water years of the reference period'),
        ('Included', 'Water years with fewer days than the minimum are flagged No. Their totals are still '
                     'listed, but indices, anomalies and the annual residual mass are left blank'),
    ]
    return pd.DataFrame(rows, columns=['Setting', 'Value']).astype({'Value': str})
