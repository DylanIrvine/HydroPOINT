# HydroPOINT

SILO climate at a point, collated to daily, monthly and water-year tables in one
Excel workbook, with rainfall metrics and plots.

Live app: https://hydropoint.streamlit.app/

Current version: 0.2.3

It is the single-location sibling of HydroSILO (https://hydrosilo.streamlit.app/),
which averages SILO climate over a catchment.

## Using it

1. Enter a latitude and longitude and a date range (no email needed: the app
   uses its own SILO account). Optionally pad the start by up to 20 years.
2. Choose the first month of the water year, the minimum number of days for a
   water year to be included, and the reference period (the entire record, or a
   range of water years).
3. Set the thresholds: rain day (mm), and the temperature and spell-length
   thresholds.
4. Optionally add a daily rain gauge file and BoM daily Tmax and Tmin files.
5. Run, then download the workbook, single figures, or everything as a zip.

Changing a threshold and pressing Run again does not download from SILO again.
Only a new grid cell or date range does.

## What the workbook holds

- **Daily.** Every variable in the SILO 'alldata' format (the source or quality
  columns are left out), excess water against FAO56 and against Morton
  wet-environment PET, rain totals over 3, 7, 14 and 30 days, the rain residual
  mass curve, a rain day flag, and running counts of consecutive rain days, dry
  days, days with Tmin below the threshold and days with Tmax above it.
- **Monthly.** A total or a mean for every variable, rain days, and the rain
  residual mass against both the mean of all months and the mean for each
  calendar month.
- **Annual.** One row per water year: a total or a mean for every variable,
  rain days, longest wet and dry spells, number of rain spells, largest 1, 3, 7, 14 and 30-day rain, PCI,
  seasonality index, wet season share, temperature threshold counts and spells,
  anomalies from the reference mean, and the annual residual mass.
- **Settings.** Every choice made in the run, plus short definitions, so a run
  can be repeated.

## Method notes

- **Location.** SILO Data Drill is a 0.05 degree grid. The point is snapped to
  the centre of its grid cell, and both are written to the Settings sheet.
- **Water year.** Named by the calendar year it starts in. With a September
  start, September 2000 to August 2001 is water year 2000.
- **Excess water.** Daily rain less daily PET, set to zero where negative, then
  summed.
- **Rain day.** Rain at or above the threshold (1 mm by default). A threshold of
  0 counts any rain above zero.
- **Spells.** Annual spell values count runs inside each water year only, so a
  run that crosses the first day of the water year is split.
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
- **Temperature files.** Bureau of Meteorology daily maximum (IDCJAC0010) and
  minimum (IDCJAC0011) temperature downloads. The observed value is used where
  it exists, including values not yet quality controlled, and SILO fills the
  gaps. The observed and SILO values and the source of each day are kept in
  their own columns. SILO PET is not recalculated. Where observed Tmax is used,
  the SILO RH at Tmax is rescaled to it before the wet-bulb temperature is
  calculated.
- **Wet-bulb temperature.** Stull (2011), from Tmax and RH at Tmax. Days
  outside the range the equation was fitted for are left blank.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Repository layout

```
HydroPOINT/
  app.py                    Streamlit front end
  hydropoint/
    silo.py                 Data Drill download and parser, grid snap, padding
    gauge.py                gauge file reader and the gauge/SILO merge
    metrics.py              daily, monthly and water-year calculations
    pipeline.py             runs the steps in order, builds the Settings table
    plots.py                figures
    workbook.py             xlsx writer
    run_counter.py          shared run total (Upstash Redis over REST)
  tests/                    pytest suite (no network needed)
  logo/                     header logo, browser-tab icon and svg source
  requirements.txt
  .streamlit/config.toml    dark theme
  LICENSE
```

## Privacy and the run counter

- A gauge file is read into memory only. Results are held in memory for the
  session. Nothing is written to a database or permanent storage.
- To get the climate, the app sends SILO the grid cell coordinates and the date
  range. SILO asks for an email as the username; the app uses its own account
  (dylan.irvine.apps@gmail.com), so users are not asked for theirs. To use
  another account when running your own copy, set the `SILO_USERNAME`
  environment variable.
- The only thing recorded is a running total of completed runs, kept in an
  Upstash Redis database under the key `hydropoint_run_count`.

The counter is optional. To turn it on, add this to the app's Secrets on
Streamlit Cloud, or to `.streamlit/secrets.toml` locally:

```
[upstash]
url = "https://<name>.upstash.io"
token = "<REST token>"
```

`.streamlit/secrets.toml` is in `.gitignore`.

## Tests

```bash
pip install pytest openpyxl
pytest tests/
```

## How to cite

Irvine, D.J. (2026). HydroPOINT (version 0.2.3) [Web application]. Charles Darwin
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
