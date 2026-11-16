# figures

import calendar

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches
import matplotlib.ticker
import matplotlib.transforms as mtransforms
import numpy as np

from .metrics import WY, MONTHS, RESIDUAL, MONTHLY_RESIDUAL, day_of_water_year
from .silo import RAIN, PET_FAO, PET_MWET
from . import smooth

YELLOW, ORANGE, RED, PURPLE, BLUE, GREEN, GREY = (
    '#FCB711', '#F37021', '#CC004C', '#6460AA', '#0089D0', '#0DB14B', '#808080')
HIGHLIGHT = [RED, BLUE, ORANGE, GREEN, PURPLE, YELLOW]
WATERMARK = 'Dylan Irvine, Charles Darwin University'
RANGE_LABEL = r'$p_{10}$ to $p_{90}$'
P_SYM, T_SYM = '$P$', '$T$'
TMAX_SYM, TMIN_SYM = r'$T_\mathrm{max}$', r'$T_\mathrm{min}$'

# Oliver (1980) PCI classes: upper limit, label, colour
PCI_CLASSES = [
    (10, 'PCI \u2264 10', GREEN),
    (15, '10 < PCI \u2264 15', YELLOW),
    (20, '15 < PCI \u2264 20', ORANGE),
    (np.inf, 'PCI > 20', RED),
]

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
    'xtick.direction': 'inout',
    'ytick.direction': 'inout',
    'xtick.major.size': 5,
    'ytick.major.size': 5,
    # symbols in the same sans-serif font as the text
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'sans',
    'mathtext.it': 'sans:italic',
    'mathtext.cal': 'sans:italic',
})


def new_fig(width_cm=16, height_cm=9, rows=1):
    fig, axes = plt.subplots(rows, 1, figsize=(width_cm / 2.54, height_cm / 2.54), sharex=rows > 1)
    return fig, axes


def add_watermark(fig):
    # credit line below the plot, bottom left
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
    # legend above the plot
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1), ncols=ncols, borderaxespad=0.2,
              handlelength=1.5, columnspacing=1.2)


def shade_reference(ax, s):
    # grey band over the reference period
    if s['ref_mode'] == 'period' and s['_ref_years']:
        ax.axvspan(min(s['_ref_years']) - 0.5, max(s['_ref_years']) + 0.5, color='0.9',
                   zorder=0, label='Reference period')


def year_limits(ax, years):
    # trim the x-axis to the bars
    ax.set_xlim(min(years) - 0.6, max(years) + 0.6)


def year_label(year, included):
    return str(year) if year in included else f'{year} (part year)'


def wettest_driest(annual):
    # from included years only
    inc = annual.loc[annual['Included'] == 'Yes']
    return int(inc.loc[inc[RAIN].idxmax(), WY]), int(inc.loc[inc[RAIN].idxmin(), WY])


def cumulative_rain(daily, annual, s, selected=None):
    # one line per water year. Wettest, driest and selected years highlighted
    start = s['wy_start_month']
    included = set(annual.loc[annual['Included'] == 'Yes', WY])
    # the selected year is drawn even if it is a part year
    d = daily.loc[daily[WY].isin(included | {selected}), ['Date', WY, RAIN]].copy()
    d['doy'] = day_of_water_year(d['Date'], start)
    d['cum'] = d.groupby(WY)[RAIN].cumsum()
    wide = d.pivot(index='doy', columns=WY, values='cum')

    fig, ax = new_fig()
    ax.plot(wide.index, wide[sorted(included)].to_numpy(), color='0.8', lw=0.6)
    ax.plot([], [], color='0.8', lw=0.6, label='Each year')

    ref_years = [y for y in s['_ref_years'] if y in wide.columns]
    mean = wide[ref_years].iloc[:365].mean(axis=1)
    ax.plot(mean.index, mean, color=GREY, lw=1.4, ls='--', label='Reference mean')

    wettest, driest = wettest_driest(annual)
    ax.plot(wide.index, wide[wettest], color=BLUE, lw=1.6, label=f'Wettest ({wettest})')
    ax.plot(wide.index, wide[driest], color=RED, lw=1.6, label=f'Driest ({driest})')
    if selected in wide.columns:
        ax.plot(wide.index, wide[selected], color='k', lw=1.6, label=year_label(selected, included))

    # month ticks (non-leap year)
    ticks, labels, day = [], [], 0
    for i in range(12):
        month = (start - 1 + i) % 12 + 1
        ticks.append(day)
        labels.append(MONTHS[month - 1])
        day += calendar.monthrange(2001, month)[1]
    ax.set_xticks(ticks, labels)
    ax.set_xlim(0, 365)
    ax.set_ylim(bottom=0)
    ax.set_ylabel('Cumulative rain (mm)')
    # legend inside, top left
    ax.legend(loc='upper left')
    return fig


def annual_totals(annual, column, ref_mean, ylabel, s, selected=None):
    # grey bars. Wettest, driest and selected years highlighted
    fig, ax = new_fig()
    inc = annual['Included'] == 'Yes'
    wettest, driest = wettest_driest(annual)
    ax.bar(annual.loc[inc, WY], annual.loc[inc, column], color=GREY, width=0.8)
    if (~inc).any():
        ax.bar(annual.loc[~inc, WY], annual.loc[~inc, column], color='0.88', width=0.8,
               label='Incomplete year')
    included = set(annual.loc[inc, WY])
    for year, colour, label in [(wettest, BLUE, f'Wettest ({wettest})'), (driest, RED, f'Driest ({driest})'),
                                (selected, 'k', year_label(selected, included))]:
        row = annual.loc[annual[WY] == year]
        if len(row):
            ax.bar(row[WY], row[column], color=colour, width=0.8, label=label)
    ax.axhline(ref_mean, color='k', lw=1, ls='--', label=f'Reference mean ({ref_mean:.0f})')
    year_limits(ax, annual[WY])
    ax.set_ylabel(ylabel)
    ax.set_xlabel(wy_label(s['wy_start_month']))
    legend_above(ax)
    return fig


def add_loess(ax, x, y, span, degree=1, robust=True):
    # black LOESS curve, dashed within half a span of each end, where the fit is one-sided
    x = np.asarray(x, dtype=float)
    fit = smooth.loess(x, y, span, degree, robust)
    inner = np.flatnonzero((x >= x.min() + span / 2) & (x <= x.max() - span / 2))
    style = dict(color='k', lw=1.4, zorder=3)
    # each dashed end includes the nearest solid point, so the parts join
    for part in (slice(0, inner[0] + 1), slice(inner[-1], len(x))):
        ax.plot(x[part], fit[part], ls=(0, (3, 2)), **style)
    ax.plot(x[inner], fit[inner], label=f"LOESS, {span}-year span{', quadratic' if degree == 2 else ''}", **style)
    return fit


def anomaly(annual, column, ylabel, s, up=BLUE, down=RED, selected=None, trend=None):
    # trend: None, or dict(span=, degree=, robust=) for a LOESS curve
    fig, ax = new_fig()
    a = annual.dropna(subset=[column])
    shade_reference(ax, s)
    ax.bar(a[WY], a[column], color=np.where(a[column] >= 0, up, down), width=0.8)
    row = a.loc[a[WY] == selected]
    if len(row):
        ax.bar(row[WY], row[column], color='k', width=0.8, label=str(selected))
    if trend and smooth.why_not(a[WY].tolist(), trend['span']) is None:
        add_loess(ax, a[WY], a[column], **trend)
    ax.axhline(0, color='k', lw=0.8)
    year_limits(ax, a[WY])
    ax.set_ylabel(ylabel)
    ax.set_xlabel(wy_label(s['wy_start_month']))
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
    ax.set_xlim(daily['Date'].min(), daily['Date'].max())

    right = ax.twinx()
    right.spines['right'].set_visible(True)
    if curve == 'Monthly':
        right.plot(month_dates, monthly[MONTHLY_RESIDUAL], color='k', lw=1)
    else:
        right.plot(daily['Date'], daily[RESIDUAL], color='k', lw=1)
    right.set_ylabel(f'Residual mass, {curve.lower()} (mm)')
    ax.plot([], [], color='k', lw=1, label=f'Residual mass ({curve.lower()})')
    legend_above(ax)
    return fig


def range_bars(ax, x, low, high, **kwargs):
    # error bars from low to high. Drawn about the midpoint, since a skewed
    # month can have its mean outside the percentile range
    ax.errorbar(x, (low + high) / 2, yerr=(high - low) / 2, fmt='none', ecolor=GREY,
                elinewidth=0.8, capsize=2, capthick=0.8, **kwargs)


def climatology(clim, ranges):
    fig, ax = new_fig()
    x = np.arange(12)
    ax.bar(x, clim[RAIN], color=BLUE, width=0.7, label=P_SYM)
    range_bars(ax, x, ranges['Rain p10'].to_numpy(), ranges['Rain p90'].to_numpy(), label=f'{P_SYM}, {RANGE_LABEL}')
    ax.plot(x, clim[PET_FAO], color=ORANGE, marker='o', ms=3, lw=1.2, label='FAO56 PET')
    ax.plot(x, clim[PET_MWET], color=RED, marker='s', ms=3, lw=1.2, label='Morton wet-environment PET')
    ax.set_xticks(x, [MONTHS[m - 1] for m in clim.index])
    ax.set_ylabel('Mean monthly total (mm)')
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=2)
    return fig


def boxes(ax, groups, colours, labels):
    # light fill in the line colour
    bp = ax.boxplot(groups, widths=0.6, patch_artist=True, tick_labels=labels,
                    medianprops=dict(color='k', lw=1), flierprops=dict(marker='o', ms=2, mew=0.5))
    for i, colour in enumerate(colours):
        bp['boxes'][i].set(edgecolor=colour, facecolor=matplotlib.colors.to_rgba(colour, 0.35))
        bp['fliers'][i].set_markeredgecolor(colour)
        for line in bp['whiskers'][2 * i:2 * i + 2] + bp['caps'][2 * i:2 * i + 2]:
            line.set_color(colour)
    ax.tick_params(axis='x', labelsize=7)


def lift_temperature_axis(right, bar_tops, rain_top, low, high, gap=0.04):
    # set the temperature axis so that each month's lowest temperature sits above
    # that month's rain bar, then drop the ticks below the temperatures plotted
    top = high.max() + 0.05 * (high.max() - low.min())
    bar_frac = np.asarray(bar_tops) / rain_top + gap
    bottom = min(low.min(), np.min((np.asarray(low) - bar_frac * top) / (1 - bar_frac)))
    right.set_ylim(bottom, top)
    # tick count scaled to the share of the axis the temperatures use
    share = (top - low.min()) / (top - bottom)
    locator = matplotlib.ticker.MaxNLocator(nbins=max(3, int(round(9 * share))), steps=[1, 2, 2.5, 5, 10])
    ticks = locator.tick_values(low.min(), top)
    step = ticks[1] - ticks[0]
    ticks = ticks[(ticks >= np.floor(low.min() / step) * step) & (ticks <= top)]
    right.set_yticks(ticks)
    right.set_ylim(bottom, top)
    right.spines['right'].set_bounds(ticks[0], top)


def climatology_temperature(annual, ranges, s):
    # left: mean monthly rain with Tmax and Tmin on a second axis.
    # right: water-year rain, mean Tmax and mean Tmin as boxes
    fig = plt.figure(figsize=(21 / 2.54, 9 / 2.54))
    outer = fig.add_gridspec(1, 2, width_ratios=[2.2, 1], wspace=0.32)
    ax = fig.add_subplot(outer[0, 0])
    inner = outer[0, 1].subgridspec(1, 3, wspace=0.9)
    ax_rain, ax_tmax, ax_tmin = (fig.add_subplot(inner[0, i]) for i in range(3))

    x = np.arange(12)
    ax.bar(x, ranges['Rain mean'], color=BLUE, width=0.7)
    range_bars(ax, x, ranges['Rain p10'].to_numpy(), ranges['Rain p90'].to_numpy())
    ax.set_xticks(x, [MONTHS[m - 1] for m in ranges.index])
    ax.set_xlim(-0.5, 11.5)
    rain_top = 1.05 * ranges['Rain p90'].max()
    ax.set_ylim(0, rain_top)
    ax.set_ylabel('Mean monthly rain (mm)')

    right = ax.twinx()
    right.spines['right'].set_visible(True)
    for name, colour, marker in [('Tmax', RED, 'o'), ('Tmin', ORANGE, 's')]:
        right.fill_between(x, ranges[f'{name} p10'], ranges[f'{name} p90'], color=colour, alpha=0.2, lw=0)
        right.plot(x, ranges[f'{name} mean'], color=colour, marker=marker, ms=3, lw=1.2)
    lift_temperature_axis(right, ranges['Rain mean'].to_numpy(), rain_top,
                          ranges[['Tmax p10', 'Tmin p10']].min(axis=1).to_numpy(),
                          ranges[['Tmax p90', 'Tmin p90']].max(axis=1).to_numpy())
    right.set_ylabel('Mean monthly temperature (\u00b0C)')
    # centre the label on the part of the axis with ticks
    low_frac = (right.get_yticks()[0] - right.get_ylim()[0]) / np.diff(right.get_ylim())[0]
    right.yaxis.label.set_y(0.5 * (1 + low_frac))

    # legend columns: temperature, then rain
    handles = [*right.lines[:2],
               matplotlib.patches.Patch(color='0.6', alpha=0.4, lw=0),
               ax.patches[0],
               ax.errorbar([], [], yerr=[], fmt='none', ecolor=GREY, elinewidth=0.8, capsize=2)]
    labels = [TMAX_SYM, TMIN_SYM, f'{T_SYM}, {RANGE_LABEL}', P_SYM, f'{P_SYM}, {RANGE_LABEL}']
    ax.legend(handles, labels, loc='lower left', bbox_to_anchor=(0, 1), ncols=2, borderaxespad=0.2,
              handlelength=1.5, columnspacing=1.0)

    # every included year (the whole record, not the reference period)
    inc = annual.loc[annual['Included'] == 'Yes']
    # short titles rather than y labels, which collide in panels this narrow.
    # no x tick labels; the middle panel carries the span of years
    for axis, column, colour, label in [
            (ax_rain, RAIN, BLUE, f'{P_SYM} (mm)'),
            (ax_tmax, 'Mean Tmax (degC)', RED, f'{TMAX_SYM} (\u00b0C)'),
            (ax_tmin, 'Mean Tmin (degC)', ORANGE, f'{TMIN_SYM} (\u00b0C)')]:
        boxes(axis, [inc[column].dropna()], [colour], [''])
        axis.set_title(label, fontsize=9, pad=4)
        axis.tick_params(axis='y', labelsize=7.5)
        axis.tick_params(axis='x', bottom=False)
    if len(inc):
        ax_tmax.set_xlabel(f'{int(inc[WY].min())}\u2013{int(inc[WY].max())}', fontsize=8)
    header = 'Annual totals and means' if s['wy_start_month'] == 1 else 'Water-year totals and means'
    ax_tmax.annotate(header, xy=(0.5, 1), xycoords='axes fraction', xytext=(0, 20),
                     textcoords='offset points', ha='center', va='bottom')
    return fig


def pci_plot(annual, s, selected=None):
    # PCI for each included year over the Oliver (1980) classes.
    # excluded years leave a break in the line
    fig, ax = new_fig()
    a = annual.loc[annual['Included'] == 'Yes'].dropna(subset=['PCI'])
    top = max(24.0, 1.08 * a['PCI'].max())
    low = 0
    for upper, label, colour in PCI_CLASSES:
        high = min(upper, top)
        ax.axhspan(low, high, color=colour, alpha=0.15, lw=0, zorder=0)
        ax.text(0.01, (low + high) / 2, label, color=colour, transform=ax.get_yaxis_transform(),
                ha='left', va='center', fontsize=7, zorder=3,
                bbox=dict(facecolor='white', alpha=0.85, lw=0, pad=1))
        low = upper
    line = a.set_index(WY)['PCI'].reindex(range(int(annual[WY].min()), int(annual[WY].max()) + 1))
    ax.plot(line.index, line, color=BLUE, lw=1, marker='o', ms=3.5, zorder=2)
    row = a.loc[a[WY] == selected]
    if len(row):
        ax.plot(row[WY], row['PCI'], color='k', marker='o', ms=5, ls='none', zorder=4, label=str(selected))
    ax.set_ylim(0, top)
    year_limits(ax, a[WY])
    ax.set_ylabel('Precipitation concentration index')
    ax.set_xlabel(wy_label(s['wy_start_month']))
    if ax.get_legend_handles_labels()[0]:
        legend_above(ax)
    return fig


def excess_water(annual, s, column, pet_name):
    fig, ax = new_fig()
    a = annual.loc[annual['Included'] == 'Yes']
    shade_reference(ax, s)
    ax.bar(a[WY], a[column], width=0.8, color=BLUE)
    ax.set_ylabel(f'Excess water, {pet_name} (mm)')
    ax.set_xlabel(wy_label(s['wy_start_month']))
    year_limits(ax, a[WY])
    if ax.get_legend_handles_labels()[0]:
        legend_above(ax)
    return fig
