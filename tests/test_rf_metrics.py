"""Tests for numeric CST curve summaries. No CST install required."""

from __future__ import annotations

from mcp_cst_studio.rf_metrics import (
    decimate,
    extract_curve,
    guess_frequency_unit,
    summarize_reflection,
    verdict_from_summary,
)


class _Item:
    def __init__(self, x, y, yim=None):
        self._x = x
        self._y = y
        self._yim = yim

    def get_xdata(self):
        return self._x

    def get_ydata(self):
        return self._y

    def get_array(self, key):
        if key == "yim":
            return self._yim
        raise KeyError(key)


def test_decimate_keeps_endpoints():
    x = list(range(10))
    y = [float(i) for i in x]
    curve = decimate(x, y, None, max_points=4)
    assert curve["x"][0] == 0
    assert curve["x"][-1] == 9
    assert curve["n_raw"] == 10
    assert curve["n_returned"] <= 4


def test_frequency_unit_guess():
    assert guess_frequency_unit([1.0, 2.4, 6.0]) == "GHz"
    assert guess_frequency_unit([1e9, 2.4e9]) == "Hz"


def test_extract_curve_from_duck_typed_item():
    item = _Item([1.0, 2.0, 3.0], [0.5, 0.1, 0.4], [0.0, 0.0, 0.0])
    curve = extract_curve(item, max_points=10)
    assert curve is not None
    assert curve["x"] == [1.0, 2.0, 3.0]
    assert curve["y_re"][1] == 0.1


def test_summary_finds_resonance_and_bandwidth():
    # |S| linear: deep match at 2.4 GHz, -10 dB is |S| ~= 0.316
    freq = [2.2, 2.3, 2.4, 2.5, 2.6]
    re = [0.8, 0.3, 0.1, 0.3, 0.8]
    im = [0.0, 0.0, 0.0, 0.0, 0.0]
    summary = summarize_reflection(freq, re, im, f0=2.4)
    assert summary["f_res"] == 2.4
    assert summary["s_min_db"] < -10
    assert summary["bandwidth"]["f_lower"] == 2.3
    assert summary["bandwidth"]["f_upper"] == 2.5
    assert summary["zin_re"] > 0
    assert summary["verdict"]["code"] == "on_target"


def test_verdict_says_electrically_long_when_resonance_is_low():
    summary = {"s_min_db": -20, "f_res": 2.0, "threshold_db": -10}
    verdict = verdict_from_summary(summary, f0=2.4)
    assert verdict["code"] == "resonance_low"
    assert "Shorten" in verdict["action"]


def test_verdict_says_electrically_short_when_resonance_is_high():
    summary = {"s_min_db": -20, "f_res": 2.8, "threshold_db": -10}
    verdict = verdict_from_summary(summary, f0=2.4)
    assert verdict["code"] == "resonance_high"
    assert "Lengthen" in verdict["action"]
