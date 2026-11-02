"""Numeric helpers for CST 3D field samples.

No CST import. Vector components are Re/Im pairs. Poynting uses the
time-average ``0.5 * Re(E × H*)``. SAR is ``0.5 * sigma * |E|^2``.
"""

from __future__ import annotations

import math
from typing import Any

_AXES = ("x", "y", "z")


def parse_complex_vectors(values: Any, n_components: int = 3) -> list[dict[str, Any]]:
    """Turn a flat or row-wise Re/Im list into one dict per point."""
    if n_components < 1 or n_components > 3:
        raise ValueError("n_components must be 1, 2, or 3")
    flat = _flatten_numbers(values)
    stride = n_components * 2
    if not flat or len(flat) % stride != 0:
        raise ValueError(
            f"Expected groups of {stride} Re/Im values, got {len(flat)} numbers"
        )
    samples: list[dict[str, Any]] = []
    for offset in range(0, len(flat), stride):
        components: dict[str, dict[str, float]] = {}
        mag_sq = 0.0
        for index, axis in enumerate(_AXES[:n_components]):
            real = flat[offset + 2 * index]
            imag = flat[offset + 2 * index + 1]
            components[axis] = {"re": real, "im": imag}
            mag_sq += real * real + imag * imag
        samples.append({"components": components, "magnitude": math.sqrt(mag_sq)})
    return samples


def peak_sample(samples: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not samples:
        return None
    index = max(range(len(samples)), key=lambda i: float(samples[i]["magnitude"]))
    return {"index": index, "magnitude": float(samples[index]["magnitude"])}


def poynting_vector(
    electric: list[complex],
    magnetic: list[complex],
) -> dict[str, float]:
    """Time-average Poynting vector, watts per square meter when E and H are SI."""
    if len(electric) != 3 or len(magnetic) != 3:
        raise ValueError("E and H each need three components")
    crossed = _half_cross_conj(electric, magnetic)
    magnitude = math.sqrt(sum(part * part for part in crossed))
    return {
        "x": crossed[0],
        "y": crossed[1],
        "z": crossed[2],
        "magnitude": magnitude,
    }


def sar(e_magnitude: float, conductivity: float) -> float:
    """Specific absorption rate proxy ``0.5 * sigma * |E|^2``.

    ``conductivity`` is siemens per meter. Mass density is not applied.
    """
    if conductivity < 0:
        raise ValueError("conductivity must be >= 0")
    if e_magnitude < 0:
        raise ValueError("e_magnitude must be >= 0")
    return 0.5 * conductivity * e_magnitude * e_magnitude


def components_to_complex(sample: dict[str, Any]) -> list[complex]:
    comps = sample["components"]
    return [
        complex(float(comps[axis]["re"]), float(comps[axis]["im"]))
        for axis in _AXES
    ]


def _flatten_numbers(values: Any) -> list[float]:
    if values is None:
        return []
    rows = list(values)
    flat: list[float] = []
    if rows and isinstance(rows[0], (list, tuple)):
        for row in rows:
            flat.extend(float(item) for item in row)
        return flat
    return [float(item) for item in rows]


def _half_cross_conj(electric: list[complex], magnetic: list[complex]) -> list[float]:
    conj_h = [complex(part).conjugate() for part in magnetic]
    e = [complex(part) for part in electric]
    cross = [
        e[1] * conj_h[2] - e[2] * conj_h[1],
        e[2] * conj_h[0] - e[0] * conj_h[2],
        e[0] * conj_h[1] - e[1] * conj_h[0],
    ]
    return [0.5 * part.real for part in cross]
