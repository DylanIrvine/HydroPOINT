# figures. Plain text throughout: no bold, no italics

import calendar

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np

from .metrics import (WY, MONTHS, RESIDUAL, EXCESS_FAO, EXCESS_MWET,
                      day_of_water_year)
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
    last = MONTHS[(start_month - 2) % 12]
    return f'Water year ({MONTHS[start_month - 1]} to {last}), named by the year it starts'


def cumulative_rain(daily, annual, s, highlight):
    # one line per water year, with the reference-period mean and chosen years picked out
    start = s['wy_start_month']
    included = set(annual.loc[annual['Included'] == 'Yes', WY])
    d = daily.loc[daily[WY].isin(included), ['Date', WY, RAIN]].copy()
    d['doy'] = day_of_water_year(d['Date'], start)
    d['cum'] = d.groupby(WY)[RAIN].cumsum()
    wide = d.pivot(index='doy', columns=WY, values='cum')

    fig, ax = new_fig(16, 10)
    ax.plot(wide.index, wide.to_numpy(), color='0.8', lw=0.6)
    ax.plot([], [], color='0.8', lw=0.6, label='Each water year')

    ref_years = [y for y in s['_ref_years'] if y in wide.columns]
    mean = wide[ref_years].iloc[:365].mean(axis=1)
    ax.plot(mean.index, mean, color='k', lw=1.6, label='Reference mean')

    for i, year in enumerate(y for y in highlight if y in wide.columns):
        ax.plot(wide.index, wide[year], color=HIGHLIGHT[i % len(HIGHLIGHT)], lw=1.6, label=str(year))

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
    ax.set_title('Cumulative rain through the water year')
    ax.legend(loc='upper left')
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
    ax.set_title(title)
    ax.legend(loc='upper left', ncols=2)
    return fig


def anomaly(annual, column, ylabel, title, s, up=BLUE, down=RED):
    fig, ax = new_fig()
    a = annual.dropna(subset=[column])
    ax.bar(a[WY], a[column], color=np.where(a[column] >= 0, up, down), width=0.8)
    ax.axhline(0, color='k', lw=0.8)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(wy_label(s['wy_start_month']))
    ax.set_title(title)
    return fig


def residual_mass(daily, monthly):
    fig, axes = new_fig(16, 12, rows=2)
    axes[0].plot(daily['Date'], daily[RESIDUAL], color=BLUE, lw=0.8)
    axes[0].set_title('Rain residual mass, daily')
    month_dates = np.array([np.datetime64(f'{y}-{m:02d}-15') for y, m in zip(monthly['Year'], monthly['Month'])])
    axes[1].plot(month_dates, monthly['Rain residual mass, all-month mean (mm)'],
                 color=BLUE, lw=0.8, label='Against the mean of all months')
    axes[1].plot(month_dates, monthly['Rain residual mass, calendar-month mean (mm)'],
                 color=ORANGE, lw=0.8, label='Against the mean for each calendar month')
    axes[1].set_title('Rain residual mass, monthly')
    axes[1].legend(loc='upper center', bbox_to_anchor=(0.5, -0.18), ncols=2)
    for ax in axes:
        ax.axhline(0, color='k', lw=0.6)
        ax.set_ylabel('Residual mass (mm)')
    fig.tight_layout()
    return fig


def climatology(clim):
    fig, ax = new_fig()
    x = np.arange(12)
    ax.bar(x, clim[RAIN], color=BLUE, width=0.7, label='Rain')
    ax.plot(x, clim[PET_FAO], color=ORANGE, marker='o', ms=3, lw=1.2, label='FAO56 PET')
    ax.plot(x, clim[PET_MWET], color=RED, marker='s', ms=3, lw=1.2, label='Morton wet-environment PET')
    ax.set_xticks(x, [MONTHS[m - 1] for m in clim.index])
    ax.set_ylabel('Mean monthly total (mm)')
    ax.set_title('Mean monthly rain and PET over the reference period')
    ax.legend(loc='best')
    return fig


def excess_water(annual, s):
    fig, ax = new_fig()
    a = annual.loc[annual['Included'] == 'Yes']
    ax.bar(a[WY] - 0.2, a[EXCESS_FAO], width=0.4, color=BLUE, label='Rain less FAO56 PET')
    ax.bar(a[WY] + 0.2, a[EXCESS_MWET], width=0.4, color=ORANGE, label='Rain less Morton PET')
    ax.set_ylabel('Excess water (mm)')
    ax.set_xlabel(wy_label(s['wy_start_month']))
    ax.set_title('Excess water by water year (sum of daily rain less PET, where positive)')
    ax.legend(loc='upper left')
    return fig
