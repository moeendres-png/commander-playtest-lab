"""Kleine Statistik-Helfer (numpy), deterministisch über feste Seeds."""

from __future__ import annotations

import numpy as np


def icc21(a, b) -> float:
    """ICC(2,1), zwei Rater, absolute Übereinstimmung (Shrout-Fleiss)."""
    x = np.column_stack([np.asarray(a, float), np.asarray(b, float)])
    n, k = x.shape
    if n < 3:
        return float("nan")
    gm = x.mean()
    msr = k * ((x.mean(1) - gm) ** 2).sum() / (n - 1)
    msc = n * ((x.mean(0) - gm) ** 2).sum() / (k - 1)
    sse = ((x - x.mean(1, keepdims=True) - x.mean(0, keepdims=True) + gm) ** 2).sum()
    mse = sse / ((n - 1) * (k - 1))
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / den) if den else float("nan")


def rank(v):
    v = np.asarray(v, float)
    order = v.argsort(kind="mergesort")
    r = np.empty(len(v))
    r[order] = np.arange(len(v))
    # Mittelränge bei Gleichstand
    _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt))
    np.add.at(sums, inv, r)
    return (sums / cnt)[inv]


def spearman(a, b) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = rank(a), rank(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def boot_paired_spearman(y, xs: dict, B=2000, seed=20261122):
    """Spearman je Reihe x gegen y, plus gepaarte Differenzen; Perzentil-Intervalle 95 %."""
    y = np.asarray(y, float)
    keys = list(xs)
    X = {k: np.asarray(v, float) for k, v in xs.items()}
    rng = np.random.default_rng(seed)
    n = len(y)
    pts = {k: spearman(X[k], y) for k in keys}
    bs = {k: [] for k in keys}
    for _ in range(B):
        i = rng.integers(0, n, n)
        for k in keys:
            bs[k].append(spearman(X[k][i], y[i]))
    out = {}
    for k in keys:
        arr = np.array(bs[k])
        out[k] = (pts[k], float(np.nanpercentile(arr, 2.5)), float(np.nanpercentile(arr, 97.5)))
    diffs = {}
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            d = np.array(bs[keys[a]]) - np.array(bs[keys[b]])
            diffs[f"{keys[a]}-{keys[b]}"] = (
                pts[keys[a]] - pts[keys[b]],
                float(np.nanpercentile(d, 2.5)),
                float(np.nanpercentile(d, 97.5)),
            )
    return out, diffs


def auc_mw(score, label) -> float:
    """AUC = P(pos > neg) + 0,5 P(gleich), direkt gezählt."""
    s = np.asarray(score, float)
    lab = np.asarray(label, bool)
    pos, neg = s[lab], s[~lab]
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def ols(X, y):
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return beta, float(r2), pred
