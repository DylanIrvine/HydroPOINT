# HydroPOINT
# SILO climate at a point, collated to daily, monthly and water-year tables in one
# workbook, with rainfall metrics and plots. Run with: streamlit run app.py

import datetime as dt
import io
import zipfile

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from hydropoint import VERSION as APP_VERSION
from hydropoint import gauge, pipeline, plots, run_counter, silo, workbook
from hydropoint.metrics import MONTHS, WY, EXCESS_FAO
from hydropoint.silo import RAIN

# %% page setup

APP_NAME = 'HydroPOINT'
# change this if the app is deployed under a different address
APP_URL = 'https://hydropoint.streamlit.app/'

LOGO = 'logo/hydrocpoint_badge.png'
FAVICON = 'logo/hydropoint_favicon.png'

st.set_page_config(page_title=APP_NAME, page_icon=FAVICON)

# %% header

head_text, head_logo = st.columns([3, 1], vertical_alignment='center')
with head_text:
    st.title(APP_NAME)
    st.subheader('SILO climate at a point: daily, monthly and water-year summaries')
    st.write('Dylan Irvine, Charles Darwin University.')
    st.caption(f'Version {APP_VERSION}')
with head_logo:
    st.image(LOGO, width='stretch')

st.markdown(
    'Enter a location and a date range to get the SILO climate record for that point as one Excel '
    'workbook, with Daily, Monthly and Annual sheets and a Settings sheet that records every choice '
    'made. Annual values use a water year that starts in the month you choose. The start of the '
    'record can be padded by up to 20 years, which suits the warm-up needed for time series models '
    'of groundwater levels such as Pastas. A rain gauge file can be added, in which case the gauge '
    'rain is used where it exists and SILO fills the gaps.\n\n'
    'Note: HydroPOINT only works for locations in Australia.')

if 'run_count' not in st.session_state:
    st.session_state['run_count'] = run_counter.get_runs()
if st.session_state['run_count'] is not None:
    st.caption(f"This tool has been run {st.session_state['run_count']:,} times.")

with st.expander('**Privacy and data handling**'):
    st.markdown(
        '**Your data**\n'
        '- A gauge file, if you add one, is read into memory on the server. It is not saved to a '
        'database or to any permanent storage.\n'
        '- Results are held in memory for your session and discarded when it ends.\n'
        '- The results exist only in the files you download.\n\n'
        '**What is sent to SILO**\n'
        '- To get the climate data, the app sends the Queensland Government SILO service the '
        'coordinates of the grid cell, the date range, and your email address (SILO asks for an '
        'email as the username). A gauge file is not sent.\n'
        '- Your email is used for that request only. This app does not store or log it, and it is '
        'not written to the workbook.\n\n'
        '**You**\n'
        '- No login, and no record kept by this app of who you are or where you are. The app does '
        'not log IP addresses or locations.\n'
        '- The only thing recorded is a single running total: the number of completed runs. It '
        'has no link to any user, email, location or file.\n\n'
        '**What this does not cover**\n'
        '- Processing happens on the server that hosts the app, not on your computer. If you are '
        'using the public web version, your inputs travel to that host (which may be outside '
        'Australia). The hosting provider and the Streamlit framework may use their own cookies '
        'and keep their own server logs, under their own privacy policies.\n'
        '- If your data are confidential or subject to a data agreement, run the app on your own '
        'machine. The code is open source (MIT).')

with st.expander('**How to cite and references**'):
    st.write(
        'This app:\n\n'
        f'Irvine, D.J. ({dt.date.today().year}). {APP_NAME} (version {APP_VERSION}) '
        f'[Web application]. Charles Darwin University. {APP_URL}\n\n'
        'Please also cite the SILO data:\n\n'
        'Jeffrey, S.J., Carter, J.O., Moodie, K.B., and Beswick, A.R. (2001). Using spatial '
        'interpolation to construct a comprehensive archive of Australian climate data. '
        'Environmental Modelling and Software 16(4), 309-330.\n\n'
        'Queensland Government (2026). SILO - Australian climate data from 1889 to yesterday. '
        'https://www.longpaddock.qld.gov.au/silo/\n\n'
        'Indices:\n\n'
        'Oliver, J.E. (1980). Monthly precipitation distribution: a comparative index. '
        'The Professional Geographer 32(3), 300-309.\n\n'
        'Walsh, R.P.D., and Lawler, D.M. (1981). Rainfall seasonality: description, spatial '
        'patterns and change through time. Weather 36(7), 201-208.')

# %% 1. location and dates

st.header('1. Location and dates')
email = st.text_input('Your email (required by SILO)',
                      help='SILO expects an email as the username. It is used only for the '
                           'download request and is not stored or logged.')

col_lat, col_lon = st.columns(2)
latitude = col_lat.number_input('Latitude (decimal degrees, negative for south)', value=None,
                                min_value=silo.LAT_RANGE[0], max_value=silo.LAT_RANGE[1],
                                format='%.4f', placeholder='e.g. -12.4239')
longitude = col_lon.number_input('Longitude (decimal degrees)', value=None,
                                 min_value=silo.LON_RANGE[0], max_value=silo.LON_RANGE[1],
                                 format='%.4f', placeholder='e.g. 130.8925')

today = dt.date.today()
first_day = silo.SILO_FIRST_DAY.date()
col_start, col_end, col_pad = st.columns(3)
start_date = col_start.date_input('Start date', value=dt.date(1990, 1, 1),
                                  min_value=first_day, max_value=today)
end_date = col_end.date_input('End date', value=today - dt.timedelta(days=1),
                              min_value=first_day, max_value=today)
pad_years = col_pad.number_input('Years of padding before the start', value=0,
                                 min_value=0, max_value=20, step=1,
                                 help='Extra years of climate ahead of the start date, for example '
                                      'ahead of the first groundwater level in a Pastas model. '
                                      'SILO starts in 1889.')

download_start = silo.padded_start(start_date, pad_years).date()
if latitude is not None and longitude is not None:
    cell_lat, cell_lon = silo.snap_to_grid(latitude, longitude)
    st.caption(f'SILO grid cell centre: {cell_lat:.2f}, {cell_lon:.2f} (0.05 degree grid). '
               f'Data will be downloaded from {download_start} to {end_date}.')

# %% 2. water year and reference period

st.header('2. Water year and reference period')
col_wy, col_min = st.columns(2)
wy_month_name = col_wy.selectbox('First month of the water year', MONTHS, index=8)
wy_start_month = MONTHS.index(wy_month_name) + 1
min_days = col_min.number_input('Minimum days for a water year to be included', value=350,
                                min_value=1, max_value=366, step=1,
                                help='Water years with fewer days of data are flagged, and left out '
                                     'of the indices, anomalies and most plots.')
st.caption(f'Water years run from {wy_month_name} to {MONTHS[(wy_start_month - 2) % 12]} and are '
           'named by the calendar year they start in.')

ref_choice = st.radio('Reference period for means, anomalies and the residual mass curves',
                      ['Entire record', 'Set a period'], horizontal=True)
ref_start = ref_end = None
if ref_choice == 'Set a period':
    col_r1, col_r2 = st.columns(2)
    ref_start = int(col_r1.number_input('First water year of the reference period', value=1961, step=1))
    ref_end = int(col_r2.number_input('Last water year of the reference period', value=1990, step=1))

# %% 3. thresholds

st.header('3. Thresholds')
col_a, col_b = st.columns(2)
rain_day_mm = col_a.number_input('Rain day threshold (mm)', value=1.0, min_value=0.0, step=0.1,
                                 help='A rain day has at least this much rain. SILO and gauges '
                                      'both report rain below 1 mm. Use 0 to count any rain.')
rain_spell_days = col_b.number_input('Rain spell: consecutive rain days', value=3, min_value=1, step=1)
col_c, col_d = st.columns(2)
tmin_threshold = col_c.number_input('Tmin below (degC)', value=5.0, step=0.5)
tmin_spell_days = col_d.number_input('Cold spell: consecutive days with Tmin below the threshold',
                                     value=3, min_value=1, step=1)
col_e, col_f = st.columns(2)
tmax_threshold = col_e.number_input('Tmax above (degC)', value=35.0, step=0.5)
tmax_spell_days = col_f.number_input('Hot spell: consecutive days with Tmax above the threshold',
                                     value=3, min_value=1, step=1)

# %% 4. gauge file (optional)

st.header('4. Rain gauge file (optional)')
st.caption('Leave this empty to use SILO rain only. With a gauge file, the rain column uses the '
           'gauge where it has a value and SILO elsewhere. The SILO rain and the source of each '
           'day are kept in their own columns.')
gauge_file = st.file_uploader('Daily rain file (CSV), for example a Bureau of Meteorology daily '
                              'rainfall download', type=['csv', 'txt'])
gauge_daily = None
if gauge_file is not None:
    try:
        table = gauge.read_table(io.BytesIO(gauge_file.getvalue()))
        if gauge.is_bom_format(table):
            gauge_daily = gauge.bom_to_daily(table)
            st.caption('Read as a Bureau of Meteorology file: the date is built from the Year, '
                       'Month and Day columns.')
        else:
            st.dataframe(table.head(5), width='stretch')
            col_g1, col_g2, col_g3 = st.columns(3)
            date_column = col_g1.selectbox('Date column', list(table.columns))
            rain_column = col_g2.selectbox('Rain column (mm)', list(table.columns),
                                           index=min(1, len(table.columns) - 1))
            day_first = col_g3.selectbox('Date order', ['Day first', 'Year or month first']) == 'Day first'
            gauge_daily = gauge.generic_to_daily(table, date_column, rain_column, day_first)
        valid = gauge_daily.dropna(subset=[gauge.GAUGE])
        st.success(f"Gauge record: {valid['Date'].min().date()} to {valid['Date'].max().date()}, "
                   f'{len(valid):,} days with a value.')
    except Exception as error:
        gauge_daily = None
        st.error(f'Could not read the gauge file: {error}')

# %% 5. run

st.header('5. Run')
FIGURE_DPI = st.radio('Figure download resolution (dpi)', [300, 600], horizontal=True)

problems = []
if not email or '@' not in email:
    problems.append('Enter a valid email.')
if latitude is None or longitude is None:
    problems.append('Enter a latitude and a longitude.')
if start_date > end_date:
    problems.append('The start date is after the end date.')
if ref_start is not None and ref_start > ref_end:
    problems.append('The reference period ends before it starts.')
for problem in problems:
    st.info(problem)

if st.button('Run', type='primary', disabled=bool(problems)):
    try:
        cell_lat, cell_lon = silo.snap_to_grid(latitude, longitude)
        start_str = download_start.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # only go back to SILO when the cell or the dates change, so thresholds
        # can be adjusted and re-run without another download
        key = (cell_lat, cell_lon, start_str, end_str)
        if st.session_state.get('raw_key') != key:
            with st.spinner('Downloading from SILO...'):
                st.session_state['raw'] = silo.download_silo_point(cell_lat, cell_lon,
                                                                   start_str, end_str, email)
                st.session_state['raw_key'] = key

        settings = dict(
            wy_start_month=wy_start_month, min_days=int(min_days),
            rain_day_mm=float(rain_day_mm), rain_spell_days=int(rain_spell_days),
            tmin_threshold=float(tmin_threshold), tmin_spell_days=int(tmin_spell_days),
            tmax_threshold=float(tmax_threshold), tmax_spell_days=int(tmax_spell_days),
            ref_mode='period' if ref_start is not None else 'entire',
            ref_start=ref_start, ref_end=ref_end)
        with st.spinner('Calculating and writing the workbook...'):
            result = pipeline.run(st.session_state['raw'], settings, gauge_daily)
            meta = dict(latitude=latitude, longitude=longitude, cell_lat=cell_lat, cell_lon=cell_lon,
                        start=start_date, pad_years=int(pad_years),
                        gauge_name=gauge_file.name if gauge_daily is not None else None)
            table = pipeline.settings_table(result, meta)
            result['xlsx'] = workbook.build(result['daily'], result['monthly'], result['annual'], table)
            result['prefix'] = f'HydroPOINT_{cell_lat:.2f}_{cell_lon:.2f}'
            st.session_state['result'] = result

        new_total = run_counter.increment_runs()
        if new_total is not None:
            st.session_state['run_count'] = new_total
    except Exception as error:
        st.error(f'Run failed: {error}')

# %% 6. results

FIGURES = {}


def show(fig, name):
    # one render at the chosen dpi: shown on the page, offered as a download, kept for the zip
    plots.add_watermark(fig)
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=FIGURE_DPI, bbox_inches='tight')
    plt.close(fig)
    FIGURES[name] = buffer.getvalue()
    st.image(FIGURES[name], width='stretch')
    st.download_button(f'Download PNG ({FIGURE_DPI} dpi)', FIGURES[name], file_name=f'{name}.png',
                       mime='image/png', key=f'download_{name}', on_click='ignore')


if 'result' in st.session_state:
    r = st.session_state['result']
    s, annual, daily, monthly = r['settings'], r['annual'], r['daily'], r['monthly']
    included = annual.loc[annual['Included'] == 'Yes']
    prefix = r['prefix']

    st.header('6. Results')
    col1, col2, col3 = st.columns(3)
    col1.metric('Water years included', f"{len(included)} of {len(annual)}")
    col2.metric('Reference mean annual rain', f"{r['ref_means'][RAIN]:,.0f} mm")
    col3.metric('Mean rain days per year', f"{included['Rain days'].mean():.0f}")
    if 'Rain source' in daily:
        counts = daily['Rain source'].value_counts()
        st.caption(f"Rain: {counts.get('Gauge', 0):,} days from the gauge, "
                   f"{counts.get('SILO', 0):,} days filled from SILO.")

    st.download_button('Download the workbook (.xlsx)', r['xlsx'], file_name=f'{prefix}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       type='primary', on_click='ignore')

    st.subheader('Cumulative rain through the water year')
    years = list(included[WY])
    highlight = st.multiselect('Water years to highlight', years, default=years[-1:])
    show(plots.cumulative_rain(daily, annual, s, highlight), f'{prefix}_cumulative_rain')

    st.subheader('Annual rain')
    show(plots.annual_totals(annual, RAIN, r['ref_means'][RAIN], 'Rain (mm)',
                             'Rain by water year', s), f'{prefix}_annual_rain')
    show(plots.anomaly(annual, 'Rain anomaly (mm)', 'Rain anomaly (mm)',
                       'Rain anomaly from the reference mean', s), f'{prefix}_rain_anomaly')

    st.subheader('Other annual anomalies')
    choices = {
        'Excess water, FAO56 (mm)': ('Excess water FAO56 anomaly (mm)', plots.BLUE, plots.RED),
        'Excess water, Morton (mm)': ('Excess water Morton anomaly (mm)', plots.BLUE, plots.RED),
        'FAO56 PET (mm)': ('FAO56 PET anomaly (mm)', plots.RED, plots.BLUE),
        'Morton PET (mm)': ('Morton PET anomaly (mm)', plots.RED, plots.BLUE),
        'Mean Tmax (degC)': ('Tmax anomaly (degC)', plots.RED, plots.BLUE),
        'Mean Tmin (degC)': ('Tmin anomaly (degC)', plots.RED, plots.BLUE),
    }
    choice = st.selectbox('Variable', list(choices))
    column, up, down = choices[choice]
    show(plots.anomaly(annual, column, column, f'{choice}: anomaly from the reference mean',
                       s, up, down), f'{prefix}_anomaly_{column.split(" anomaly")[0].replace(" ", "_")}')

    st.subheader('Rain residual mass')
    show(plots.residual_mass(daily, monthly), f'{prefix}_residual_mass')

    st.subheader('Monthly means and excess water')
    show(plots.climatology(r['climatology']), f'{prefix}_monthly_means')
    show(plots.excess_water(annual, s), f'{prefix}_excess_water')

    st.subheader('Annual table')
    st.dataframe(annual, width='stretch', hide_index=True)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f'{prefix}.xlsx', r['xlsx'])
        for name, data in FIGURES.items():
            archive.writestr(f'{name}.png', data)
    st.download_button('Download everything (.zip)', zip_buffer.getvalue(),
                       file_name=f'{prefix}_outputs.zip', mime='application/zip', on_click='ignore')
