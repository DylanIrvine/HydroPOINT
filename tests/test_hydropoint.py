# checks that need no network. Run with: pytest tests/

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from hydropoint import gauge, metrics, pipeline, silo, workbook

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def fake_silo(start='1999-01-01', end='2004-12-31', seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end)
    out = pd.DataFrame({'Date': dates})
    out[silo.RAIN] = np.where(rng.random(len(dates)) < 0.3, rng.gamma(0.8, 12, len(dates)).round(1), 0.0)
    out[silo.PET_FAO] = 5.0
    out[silo.PET_MWET] = 6.0
    out[silo.TMAX] = 30 + rng.normal(0, 3, len(dates))
    out[silo.TMIN] = 15 + rng.normal(0, 3, len(dates))
    for name in list(silo.SILO_COLUMNS.values())[5:]:
        out[name] = 1.0
    return out


def test_water_year_named_by_start_year():
    dates = pd.to_datetime(['2000-08-31', '2000-09-01', '2001-08-31', '2001-09-01'])
    assert list(metrics.water_year(dates, 9)) == [1999, 2000, 2000, 2001]
    assert list(metrics.water_year(dates, 1)) == [2000, 2000, 2001, 2001]
    assert list(metrics.day_of_water_year(dates, 9)) == [365, 0, 364, 0]


def test_spell_stats():
    flag = [1, 1, 0, 1, 1, 1, 0, 0, 1]
    assert metrics.spell_stats(flag, 2) == (3, 2)
    assert metrics.spell_stats([0, 0], 1) == (0, 0)
    assert list(metrics.running_count(pd.Series(flag) == 1)) == [1, 2, 0, 1, 2, 3, 0, 0, 1]


def test_indices_at_their_limits():
    even = pd.Series([50.0] * 12)
    one_month = pd.Series([600.0] + [0.0] * 11)
    assert metrics.pci(even) == pytest.approx(100 / 12)
    assert metrics.pci(one_month) == pytest.approx(100)
    assert metrics.seasonality_index(even) == pytest.approx(0)
    assert metrics.seasonality_index(one_month) == pytest.approx(22 / 12)


def test_rain_day_threshold():
    rain = pd.Series([0.0, 0.2, 1.0, 5.0])
    assert list(metrics.is_rain_day(rain, 1.0)) == [False, False, True, True]
    assert list(metrics.is_rain_day(rain, 0.0)) == [False, True, True, True]


def test_grid_snap_and_padding():
    assert silo.snap_to_grid(-12.4239, 130.8925) == (-12.4, 130.9)
    assert silo.padded_start('2000-06-15', 20) == pd.Timestamp('1980-06-15')
    assert silo.padded_start('1895-01-01', 20) == silo.SILO_FIRST_DAY


def test_parse_silo_alldata():
    names = ['Date', 'Day', 'Date2', 'T.Max', 'Smx', 'T.Min', 'Smn', 'Rain', 'Srn', 'Evap', 'Sev',
             'Radn', 'Ssl', 'VP', 'Svp', 'RHmaxT', 'RHminT', 'FAO56', 'Mlake', 'Mpot', 'Mact', 'Mwet', 'Span']
    row = '{d} {n} 01-01-2020 33.0 25 24.5 25 12.4 25 6.0 25 20.0 25 30.0 25 60.0 90.0 5.1 6 7 4 6.2 6.5'
    text = '\n'.join(['"some header text"', ' '.join(names), ' '.join(['(units)'] * len(names)),
                      row.format(d=20200101, n=1), row.format(d=20200102, n=2)])
    out = silo.parse_silo_alldata(text.encode())
    assert len(out) == 2
    assert out[silo.RAIN].iloc[0] == 12.4
    assert out[silo.PET_FAO].iloc[0] == 5.1
    assert out[silo.PET_MWET].iloc[0] == 6.2
    assert out['Date'].iloc[1] == pd.Timestamp('2020-01-02')


def test_daily_columns():
    r = pipeline.run(fake_silo(), dict(wy_start_month=9))
    d = r['daily']
    assert (d[metrics.EXCESS_FAO] >= 0).all()
    wet = d[silo.RAIN] > d[silo.PET_FAO]
    assert np.allclose(d.loc[wet, metrics.EXCESS_FAO], d.loc[wet, silo.RAIN] - 5.0)
    assert d['Rain 7-day total (mm)'].iloc[6] == pytest.approx(d[silo.RAIN].iloc[:7].sum())
    assert np.isnan(d['Rain 7-day total (mm)'].iloc[5])
    # the residual mass returns to zero at the end when the mean is from the whole record
    assert d[metrics.RESIDUAL].iloc[-1] == pytest.approx(0, abs=1e-6)


def test_annual_inclusion_and_totals():
    r = pipeline.run(fake_silo(), dict(wy_start_month=9, min_days=350))
    a = r['annual'].set_index(metrics.WY)
    # Jan to Aug 1999 and Sep to Dec 2004 are part years
    assert a.loc[1998, 'Included'] == 'No' and a.loc[2004, 'Included'] == 'No'
    assert (a.loc[1999:2003, 'Included'] == 'Yes').all()
    assert np.isnan(a.loc[1998, 'PCI']) and np.isnan(a.loc[1998, 'Rain anomaly (mm)'])
    d = r['daily']
    in_2000 = (d['Date'] >= '2000-09-01') & (d['Date'] <= '2001-08-31')
    assert a.loc[2000, silo.RAIN] == pytest.approx(d.loc[in_2000, silo.RAIN].sum())
    assert a.loc[2000, 'Rain days'] == (d.loc[in_2000, silo.RAIN] >= 1.0).sum()
    assert a.loc[1999:2003, 'Rain anomaly (mm)'].sum() == pytest.approx(0, abs=1e-6)


def test_reference_period():
    r = pipeline.run(fake_silo(), dict(wy_start_month=9, ref_mode='period', ref_start=2000, ref_end=2001))
    a = r['annual'].set_index(metrics.WY)
    assert r['ref_means'][silo.RAIN] == pytest.approx(a.loc[2000:2001, silo.RAIN].mean())
    with pytest.raises(ValueError):
        pipeline.run(fake_silo(), dict(ref_mode='period', ref_start=1950, ref_end=1960))


def test_gauge_fill():
    bom = ('Product code,Bureau of Meteorology station number,Year,Month,Day,'
           'Rainfall amount (millimetres),Period over which rainfall was measured (days),Quality\n'
           'IDCJAC0009,014015,1999,01,01,7.0,1,Y\n'
           'IDCJAC0009,014015,1999,01,02,,,\n'
           'IDCJAC0009,014015,1999,01,03,30.0,2,Y\n'
           'IDCJAC0009,014015,1999,01,04,0.0,,Y\n')
    table = gauge.read_table(io.StringIO(bom))
    assert gauge.is_bom_format(table)
    g = gauge.bom_to_daily(table)
    r = pipeline.run(fake_silo(), dict(), g)
    d = r['daily'].set_index('Date')
    assert d.loc['1999-01-01', silo.RAIN] == 7.0 and d.loc['1999-01-01', 'Rain source'] == 'Gauge'
    # a blank day and a two-day total both fall back to SILO
    for day in ('1999-01-02', '1999-01-03', '1999-01-05'):
        assert d.loc[day, 'Rain source'] == 'SILO'
        assert d.loc[day, silo.RAIN] == d.loc[day, gauge.SILO_RAIN]
    assert d.loc['1999-01-04', 'Rain source'] == 'Gauge'


def test_workbook_sheets():
    import openpyxl
    r = pipeline.run(fake_silo(), dict())
    meta = dict(latitude=-12.42, longitude=130.89, cell_lat=-12.4, cell_lon=130.9,
                start='1999-01-01', pad_years=0, gauge_name=None)
    data = workbook.build(r['daily'], r['monthly'], r['annual'], pipeline.settings_table(r, meta))
    book = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    assert book.sheetnames == ['Daily', 'Monthly', 'Annual', 'Settings']


def test_app_boots():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == 'HydroPOINT'


def test_results_section_renders():
    r = pipeline.run(fake_silo(), dict())
    r['xlsx'] = b'x'
    r['prefix'] = 'HydroPOINT_test'
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state['result'] = r
    at.run()
    assert not at.exception
    assert any(h.value == '6. Results' for h in at.header)
