"""Numeric helpers for CST result curves.

These functions do not import CST. They turn x/y samples into the small
summary an agent needs to decide the next design step.
"""

from __future__ import annotations

import math
from typing import Any


def _as_floats(values: Any) -> list[float]:
    out: list[float] = []
    for value in list(values):
        out.append(float(value))
    return out


def decimate(
    x: list[float],
    y_re: list[float],
    y_im: list[float] | None,
    max_points: int,
) -> dict[str, Any]:
    """Keep endpoints and stride the curve so the payload stays small."""
    n = min(len(x), len(y_re))
    if y_im is not None:
        n = min(n, len(y_im))
    if n <= 0:
        return {"x": [], "y_re": [], "n_raw": 0, "n_returned": 0}
    if max_points < 2:
        max_points = 2
    if n > max_points:
        step = math.ceil(n / max_points)
        index = list(range(0, n, step))
        if index[-1] != n - 1:
            index.append(n - 1)
    else:
        index = list(range(n))
    curve: dict[str, Any] = {
        "x": [x[i] for i in index],
        "y_re": [y_re[i] for i in index],
        "n_raw": n,
        "n_returned": len(index),
        "unit_guess": guess_frequency_unit(x[:n]),
    }
    if y_im is not None:
        curve["y_im"] = [y_im[i] for i in index]
    return curve


def guess_frequency_unit(x: list[float]) -> str:
    """CST x-axes follow the project unit. Guess so the agent does not assume Hz."""
    if not x:
        return "unknown"
    peak = max(abs(v) for v in x)
    if peak > 1e6:
        return "Hz"
    if peak > 1e3:
        return "MHz"
    return "GHz"


def extract_curve(item: Any, max_points: int = 201) -> dict[str, Any] | None:
    """Read x/y from a cst.results item or any object with the same methods."""
    x = _call_series(item, ("get_xdata", "get_x_data"))
    y_re = _call_series(item, ("get_ydata", "get_y_data"))
    y_im = _call_series(item, ("get_yimag", "get_yim_data"))

    if x is None or y_re is None:
        x = _call_array(item, "x")
        y_re = _call_array(item, "y")
        y_im = _call_array(item, "yim")

    if x is None or y_re is None:
        paired = _call_method(item, "get_data")
        if paired:
            try:
                xs, ys = zip(*list(paired), strict=False)
                x = _as_floats(xs)
                y_re = _as_floats(ys)
            except (TypeError, ValueError):
                return None

    if x is None or y_re is None:
        return None
    im = y_im if y_im else None
    return decimate(x, y_re, im, max_points)


def _call_method(item: Any, name: str) -> Any:
    fn = getattr(item, name, None)
    if not callable(fn):
        return None
    try:
        return fn()
    except TypeError:
        return None


def _call_series(item: Any, names: tuple[str, ...]) -> list[float] | None:
    for name in names:
        raw = _call_method(item, name)
        if raw is None:
            continue
        try:
            return _as_floats(raw)
        except (TypeError, ValueError):
            continue
    return None


def _call_array(item: Any, key: str) -> list[float] | None:
    fn = getattr(item, "get_array", None)
    if not callable(fn):
        return None
    try:
        raw = fn(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return _as_floats(raw)
    except (TypeError, ValueError):
        return None


def _to_db(y_re: list[float], y_im: list[float] | None) -> list[float]:
    if y_im:
        db: list[float] = []
        for re, im in zip(y_re, y_im, strict=False):
            mag = math.hypot(re, im)
            db.append(20.0 * math.log10(mag) if mag > 1e-15 else -300.0)
        return db
    # Already a dB trace (typical ASCII export) when values are not linear |S|<=1.
    if y_re and max(y_re) <= 0.0:
        return list(y_re)
    db = []
    for mag in y_re:
        amp = abs(mag)
        db.append(20.0 * math.log10(amp) if amp > 1e-15 else -300.0)
    return db


def summarize_reflection(
    x: list[float],
    y_re: list[float],
    y_im: list[float] | None = None,
    *,
    z0: float = 50.0,
    threshold_db: float = -10.0,
    f0: float | None = None,
) -> dict[str, Any]:
    """Resonance, match, and bandwidth from one reflection trace."""
    n = min(len(x), len(y_re))
    if y_im is not None:
        n = min(n, len(y_im))
    if n < 1:
        return {"status": "empty"}
    xs = x[:n]
    re = y_re[:n]
    im = y_im[:n] if y_im is not None else None
    db = _to_db(re, im)
    i_min = min(range(n), key=lambda i: db[i])
    band = _contiguous_band(xs, db, i_min, threshold_db)
    summary: dict[str, Any] = {
        "n_points": n,
        "f_start": xs[0],
        "f_stop": xs[-1],
        "f_res": xs[i_min],
        "s_min_db": db[i_min],
        "threshold_db": threshold_db,
        "unit_guess": guess_frequency_unit(xs),
        "bandwidth": band,
    }
    if im is not None:
        gamma = complex(re[i_min], im[i_min])
        mag = abs(gamma)
        if mag < 0.999:
            summary["vswr_at_resonance"] = (1.0 + mag) / (1.0 - mag)
        denom = 1.0 - gamma
        if abs(denom) > 1e-12:
            zin = z0 * (1.0 + gamma) / denom
            summary["zin_re"] = zin.real
            summary["zin_im"] = zin.imag
            summary["z0"] = z0
    summary["verdict"] = verdict_from_summary(summary, f0=f0)
    return summary


def _contiguous_band(
    x: list[float],
    db: list[float],
    i_min: int,
    threshold_db: float,
) -> dict[str, float] | None:
    if db[i_min] > threshold_db:
        return None
    lo = i_min
    while lo > 0 and db[lo - 1] <= threshold_db:
        lo -= 1
    hi = i_min
    while hi + 1 < len(db) and db[hi + 1] <= threshold_db:
        hi += 1
    width = x[hi] - x[lo]
    center = x[i_min]
    frac = (width / center * 100.0) if center else 0.0
    return {
        "f_lower": x[lo],
        "f_upper": x[hi],
        "width": width,
        "fractional_percent": frac,
    }


def verdict_from_summary(summary: dict[str, Any], f0: float | None = None) -> dict[str, str]:
    """Short RF call so the agent knows whether to lengthen, shorten, or stop."""
    s_min = summary.get("s_min_db")
    f_res = summary.get("f_res")
    if s_min is None or f_res is None:
        return {"code": "unknown", "action": "Read the reflection trace before changing geometry."}
    matched = s_min <= float(summary.get("threshold_db", -10.0))
    if f0 is None or f0 == 0:
        if matched:
            return {
                "code": "matched",
                "action": "Match meets the threshold at the deepest return loss. Check bandwidth and farfield next.",
            }
        return {
            "code": "poor_match",
            "action": "Return loss is shallow. Check feed geometry and reference impedance before chasing length.",
        }
    # Lower resonance means the structure is electrically long.
    ratio = (float(f_res) - float(f0)) / float(f0)
    if abs(ratio) <= 0.02 and matched:
        return {
            "code": "on_target",
            "action": "Resonance and match are inside the target. Stop length tuning and read the farfield.",
        }
    if ratio < -0.02:
        return {
            "code": "resonance_low",
            "action": "Resonance is below target, so the structure is electrically long. Shorten the radiator.",
        }
    if ratio > 0.02:
        return {
            "code": "resonance_high",
            "action": "Resonance is above target, so the structure is electrically short. Lengthen the radiator.",
        }
    return {
        "code": "frequency_ok_match_poor",
        "action": "Frequency is close but the match is poor. Tune the feed or add a matching network, not the length.",
    }
