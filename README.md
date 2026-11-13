# HydroPOINT

SILO climate at a point, collated to daily, monthly and water-year tables in one
Excel workbook, with rainfall metrics and plots.

Not deployed yet. The citation in the app assumes https://hydropoint.streamlit.app/
(set by `APP_URL` near the top of `app.py`).

Current version: 0.1.0 (set by `VERSION` in `hydropoint/__init__.py`).

It is the single-location sibling of HydroSILO (https://hydrosilo.streamlit.app/),
which averages SILO climate over a catchment.

## Using it

1. Enter an email (SILO asks for one as the username), a latitude and longitude,
   and a date range. Optionally pad the start by up to 20 years.
2. Choose the first month of the water year, the minimum number of days for a
   water year to be included, and the reference period (the entire record, or a
   range of water years).
3. Set the thresholds: rain day (mm), and the temperature and spell-length
   thresholds.
4. Optionally add a daily rain gauge file.
5. Run, then download the workbook, single figures, or everything as a zip.

Changing a threshold and pressing Run again does not download from SILO again.
Only a new grid cell or date range does.

## What the workbook holds

- **Daily.** The SILO variables, excess water against FAO56 and against Morton
  wet-environment PET, rain totals over 3, 7, 14 and 30 days, the rain residual
  mass curve, a rain day flag, and running counts of consecutive rain days, dry
  days, days with Tmin below the threshold and days with Tmax above it.
- **Monthly.** Totals and means for each month, rain days, and the rain residual
  mass against both the mean of all months and the mean for each calendar month.
- **Annual.** One row per water year: totals, rain days, longest wet and dry
  spells, number of rain spells, largest 1, 3, 7, 14 and 30-day rain, PCI,
  seasonality index, wet season share, temperature threshold counts and spells,
  anomalies from the reference mean, and the annual residual mass.
- **Settings.** Every choice made in the run, plus short definitions, so a run
  can be repeated.

## Choices worth knowing

- **Location.** SILO Data Drill is a 0.05 degree grid. The point is snapped to
  the centre of its grid cell, and both are written to the Settings sheet.
- **Water year.** Named by the calendar year it starts in. With a September
  start, September 2000 to August 2001 is water year 2000.
- **Excess water.** Daily rain less daily PET, set to zero where negative, then
  summed. A sum of daily values is not the same as monthly rain less monthly PET.
- **Rain day.** Rain at or above the threshold (1 mm by default). A threshold of
  0 counts any rain above zero.
- **Spells.** Annual spell values count runs inside each water year only, so a
  run that crosses the first day of the water year is split. Start the water
  year in the dry season and this rarely matters.
- **Included years.** A water year with fewer days of data than the minimum is
  flagged. Its totals are listed, but its indices, anomalies and residual mass
  are left blank, and it is left out of the reference means.
- **Wet season.** The six consecutive months with the most rain on average over
  the reference period. The same months are used for every year.
- **Gauge file.** A Bureau of Meteorology daily rainfall download is recognised
  from its Year, Month and Day columns. Other CSV files ask for the date and
  rain columns. The Rain column uses the gauge where it has a value and SILO
  elsewhere, with the SILO rain and the source of each day kept in their own
  columns. A gauge total measured over more than one day is treated as a gap.
  All rainfall metrics use the merged Rain column.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Repository layout

```
hydropoint-app/
  app.py                    Streamlit front end
  hydropoint/
    silo.py                 Data Drill download and parser, grid snap, padding
    gauge.py                gauge file reader and the gauge/SILO merge
    metrics.py              daily, monthly and water-year calculations
    pipeline.py             runs the steps in order, builds the Settings table
    plots.py                figures
    workbook.py             xlsx writer
    run_counter.py          shared run total (Upstash Redis over REST)
  tests/                    non-network pytest suite
  logo/                     header logo and browser-tab icon
  requirements.txt
  .streamlit/config.toml    dark theme
  LICENSE
```

## Privacy and the run counter

- A gauge file is read into memory only. Results are held in memory for the
  session. Nothing is written to a database or permanent storage.
- To get the climate, the app sends SILO the grid cell coordinates, the date
  range and the user's email. The email is not stored, logged or written to the
  workbook.
- The only thing recorded is a running total of completed runs, kept in an
  Upstash Redis database under the key `hydropoint_run_count`.

The counter is optional. To turn it on, add this to the app's Secrets on
Streamlit Cloud, or to `.streamlit/secrets.toml` locally:

```
[upstash]
url = "https://<name>.upstash.io"
token = "<REST token>"
```

`.streamlit/secrets.toml` is in `.gitignore`. Never commit the token.

## Tests

```bash
pip install pytest openpyxl
pytest tests/
```

The tests do not contact SILO. The download itself uses the same request and
parser as HydroSILO.

## How to cite

Irvine, D.J. (2026). HydroPOINT (version 0.1.0) [Web application]. Charles Darwin
University. https://hydropoint.streamlit.app/

Please also cite the SILO data:

Jeffrey, S.J., Carter, J.O., Moodie, K.B., and Beswick, A.R. (2001). Using
spatial interpolation to construct a comprehensive archive of Australian climate
data. Environmental Modelling and Software 16(4), 309-330.

## Licence

MIT. See `LICENSE`.

## Credits

Dylan Irvine, Charles Darwin University. Climate data are from SILO, hosted by
the Queensland Government.
