# figures. Plain text throughout: no bold, no italics

import calendar

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np

from .metrics import WY, MONTHS, RESIDUAL, MONTHLY_RESIDUAL, day_of_water_year
from .silo import RAIN, PET_FAO, PET_MWET

YELLOW, ORANGE, RED, PURPLE, BLUE, GREEN, GREY = (
    '#FCB711', '#F37021', '#CC004C', '#6460AA', '#0089D0', '#0DB14B', '#808080')
HIGHLIGHT = [RED, BLUE, ORANGE, GREEN, PURPLE, YELLOW]
WATERMARK = 'Dylan Irvine, Charles Darwin University'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Liberation Sans', 'DejaVu Sans'],
    'font.size': 9,
    'font.weight': 'normal',
    'axes.titleweight': 'normal',
    'axes.labelweight': 'normal',
    'axes.titlesize': 10,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'legend.frameon': False,
})


def new_fig(width_cm=16, height_cm=9, rows=1):
    fig, axes = plt.subplots(rows, 1, figsize=(width_cm / 2.54, height_cm / 2.54), sharex=rows > 1)
    return fig, axes


def add_watermark(fig):
    # small grey line in its own strip just below the drawn area, bottom left,
    # so it can be cropped off without touching the plot
    fig.canvas.draw()
    box = fig.get_tightbbox(fig.canvas.get_renderer())
    width, height = fig.get_size_inches()
    below = fig.transFigure + mtransforms.ScaledTranslation(0, -5 / 72, fig.dpi_scale_trans)
    fig.text(box.x0 / width, box.y0 / height, WATERMARK, transform=below,
             ha='left', va='top', fontsize=6, color='0.5')


def wy_label(start_month):
    if start_month == 1:
        return 'Year'
    last = MONTHS[(start_month - 2) % 12]
    return f'Water year ({MONTHS[start_month - 1]} to {last}), named by the year it starts in'


def legend_above(ax, ncols=3):
    # legend in the top right margin, clear of the data. Titles sit on the left
    ax.legend(loc='lower right', bbox_to_anchor=(1, 1), ncols=ncols, borderaxespad=0.2,
              handlelength=1.5, columnspacing=1.2)


def shade_reference(ax, s):
    # light grey band over the reference period, when one has been set
    if s['ref_mode'] == 'period' and s['_ref_years']:
        ax.axvspan(min(s['_ref_years']) - 0.5, max(s['_ref_years']) + 0.5, color='0.9',
                   zorder=0, label='Reference period')


def cumulative_rain(daily, annual, s, selected=None):
    # one grey line per water year, with the wettest, driest and one chosen year picked out
    start = s['wy_start_month']
    inc = annual.loc[annual['Included'] == 'Yes']
    d = daily.loc[daily[WY].isin(set(inc[WY])), ['Date', WY, RAIN]].copy()
    d['doy'] = day_of_water_year(d['Date'], start)
    d['cum'] = d.groupby(WY)[RAIN].cumsum()
    wide = d.pivot(index='doy', columns=WY, values='cum')

    fig, ax = new_fig(16, 10)
    ax.plot(wide.index, wide.to_numpy(), color='0.8', lw=0.6)
    ax.plot([], [], color='0.8', lw=0.6, label='Each year')

    ref_years = [y for y in s['_ref_years'] if y in wide.columns]
    mean = wide[ref_years].iloc[:365].mean(axis=1)
    ax.plot(mean.index, mean, color=GREY, lw=1.4, ls='--', label='Reference mean')

    wettest = int(inc.loc[inc[RAIN].idxmax(), WY])
    driest = int(inc.loc[inc[RAIN].idxmin(), WY])
    ax.plot(wide.index, wide[wettest], color=BLUE, lw=1.6, label=f'Wettest ({wettest})')
    ax.plot(wide.index, wide[driest], color=RED, lw=1.6, label=f'Driest ({driest})')
    if selected in wide.columns:
        ax.plot(wide.index, wide[selected], color='k', lw=1.6, label=str(selected))

    # month ticks for a year that is not a leap year
    ticks, labels, day = [], [], 0
    for i in range(12):
        month = (start - 1 + i) % 12 + 1
        ticks.append(day)
        labels.append(MONTHS[month - 1])
        day += calendar.monthrange(2001, month)[1]
    ax.set_xticks(ticks, labels)
    ax.set_xlim(0, 366)
    ax.set_ylim(bottom=0)
    ax.set_ylabel('Cumulative rain (mm)')
    # five entries need the full width, so this plot has no title
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1), ncols=5, borderaxespad=0.2,
              handlelength=1.5, columnspacing=1.2)
    return fig


def annual_totals(annual, column, ref_mean, ylabel, title, s, colour=BLUE):
    fig, ax = new_fig()
    inc = annual['Included'] == 'Yes'
    ax.bar(annual.loc[inc, WY], annual.loc[inc, column], color=colour, width=0.8)
    if (~inc).any():
        ax.bar(annual.loc[~inc, WY], annual.loc[~inc, column], color='0.8', width=0.8,
               label='Incomplete year')
    ax.axhline(ref_mean, color='k', lw=1, ls='--', label=f'Reference mean ({ref_mean:.0f})')
    ax.set_ylabel(ylabel)
    ax.set_xlabel(wy_label(s['wy_start_month']))
    ax.set_title(title, loc='left')
    legend_above(ax)
    return fig


def anomaly(annual, column, ylabel, title, s, up=BLUE, down=RED):
    fig, ax = new_fig()
    a = annual.dropna(subset=[column])
    shade_reference(ax, s)
    ax.bar(a[WY], a[column], color=np.where(a[column] >= 0, up, down), width=0.8)
    ax.axhline(0, color='k', lw=0.8)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(wy_label(s['wy_start_month']))
    ax.set_title(title, loc='left')
    if ax.get_legend_handles_labels()[0]:
        legend_above(ax)
    return fig


def residual_mass(daily, monthly, bars='Monthly', curve='Monthly'):
    # rain as bars on the left axis, the residual mass curve on the right axis
    month_dates = np.array([np.datetime64(f'{y}-{m:02d}-15') for y, m in zip(monthly['Year'], monthly['Month'])])
    fig, ax = new_fig()
    if bars == 'Monthly':
        ax.bar(month_dates, monthly[RAIN], width=np.timedelta64(25, 'D'), color=BLUE, label='Monthly rain')
    else:
        wet = daily[RAIN] > 0
        ax.vlines(daily.loc[wet, 'Date'], 0, daily.loc[wet, RAIN], color=BLUE, lw=0.5, label='Daily rain')
    ax.set_ylabel(f'{bars} rain (mm)')
    ax.set_ylim(bottom=0)

    right = ax.twinx()
    right.spines['right'].set_visible(True)
    if curve == 'Monthly':
        right.plot(month_dates, monthly[MONTHLY_RESIDUAL], color='k', lw=1)
    else:
        right.plot(daily['Date'], daily[RESIDUAL], color='k', lw=1)
    right.set_ylabel(f'Residual mass, {curve.lower()} (mm)')
    ax.plot([], [], color='k', lw=1, label=f'Residual mass ({curve.lower()})')
    ax.set_title('Rain and rain residual mass', loc='left')
    legend_above(ax)
    return fig


def climatology(clim):
    fig, ax = new_fig()
    x = np.arange(12)
    ax.bar(x, clim[RAIN], color=BLUE, width=0.7, label='Rain')
    ax.plot(x, clim[PET_FAO], color=ORANGE, marker='o', ms=3, lw=1.2, label='FAO56 PET')
    ax.plot(x, clim[PET_MWET], color=RED, marker='s', ms=3, lw=1.2, label='Morton wet-environment PET')
    ax.set_xticks(x, [MONTHS[m - 1] for m in clim.index])
    ax.set_ylabel('Mean monthly total (mm)')
    ax.set_title('Monthly means', loc='left')
    legend_above(ax)
    return fig


def excess_water(annual, s, column, pet_name):
    fig, ax = new_fig()
    a = annual.loc[annual['Included'] == 'Yes']
    shade_reference(ax, s)
    ax.bar(a[WY], a[column], width=0.8, color=BLUE)
    ax.set_ylabel('Excess water (mm)')
    ax.set_xlabel(wy_label(s['wy_start_month']))
    ax.set_title(f'Excess water, {pet_name}', loc='left')
    if ax.get_legend_handles_labels()[0]:
        legend_above(ax)
    return fig
