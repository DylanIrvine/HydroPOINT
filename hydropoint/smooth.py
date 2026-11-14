# LOESS smoother (Cleveland 1979) for the annual anomaly plots

import numpy as np

MIN_YEARS = 15          # fewer included years than this and no curve is drawn
MAX_SPAN_SHARE = 0.8    # nor when the span covers more of the record than this
ROBUST_ITERATIONS = 3   # as in Cleveland (1979) and statsmodels


def neighbours(x, span_years):
    # points in each local fit: the span in years times the density of points
    record = x.max() - x.min() + 1
    return int(min(len(x), max(3, round(span_years * len(x) / record))))


def loess(x, y, span_years, degree=1, robust=True):
    # local polynomial fit at each x, tricube weights over the k nearest points.
    # robust: bisquare weights on the residuals, refitted ROBUST_ITERATIONS times
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    k = max(neighbours(x, span_years), degree + 2)
    k = min(k, n)
    robustness = np.ones(n)
    fitted = np.empty(n)
    for _ in range(1 + (ROBUST_ITERATIONS if robust else 0)):
        for i in range(n):
            distance = np.abs(x - x[i])
            h = np.sort(distance)[k - 1]
            w = np.clip(1 - (distance / h) ** 3, 0, None) ** 3 * robustness if h > 0 else robustness.copy()
            dx = x - x[i]
            design = np.vander(dx, degree + 1, increasing=True)
            sw = np.sqrt(w)
            coef = np.linalg.lstsq(design * sw[:, None], y * sw, rcond=None)[0]
            fitted[i] = coef[0]
        residual = y - fitted
        scale = 6 * np.median(np.abs(residual))
        if scale == 0:
            break
        robustness = np.clip(1 - (residual / scale) ** 2, 0, None) ** 2
    return fitted


def why_not(x, span_years):
    # reason the curve is not drawn, or None
    if len(x) < MIN_YEARS:
        return f'fewer than {MIN_YEARS} included years'
    record = max(x) - min(x) + 1
    if span_years > MAX_SPAN_SHARE * record:
        return f'the span is more than {MAX_SPAN_SHARE:.0%} of the {record}-year record'
    return None
