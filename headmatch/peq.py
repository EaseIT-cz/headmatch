from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal

import numpy as np
from scipy import signal

from .signals import fractional_octave_smoothing

FillPolicy = Literal["up_to_n", "exact_n"]
FilterFamily = Literal["peq", "graphic_eq"]


@dataclass(frozen=True)
class FilterBudget:
    family: FilterFamily = "peq"
    max_filters: int = 8
    fill_policy: FillPolicy = "up_to_n"
    profile: str | None = None

    def normalized(self) -> "FilterBudget":
        family = self.family
        fill_policy = self.fill_policy
        profile = self.profile
        max_filters = max(int(self.max_filters), 0)
        if family == "graphic_eq":
            fill_policy = "exact_n"
            profile = profile or _default_graphic_eq_profile_name(max_filters)
        return FilterBudget(
            family=family,
            max_filters=max_filters,
            fill_policy=fill_policy,
            profile=profile,
        )


@dataclass(frozen=True)
class FitObjective:
    freqs_hz: np.ndarray
    eq_target_db: np.ndarray
    sample_rate: int
    weights: np.ndarray

    @classmethod
    def from_target(
        cls,
        freqs_hz: np.ndarray,
        target_eq_db: np.ndarray,
        sample_rate: int,
        weights: np.ndarray | None = None,
    ) -> "FitObjective":
        eq_target = fractional_octave_smoothing(freqs_hz, target_eq_db, fraction=8)
        return cls(
            freqs_hz=freqs_hz,
            eq_target_db=eq_target,
            sample_rate=sample_rate,
            weights=weights if weights is not None else _residual_priority_weights(freqs_hz),
        )

    def residual_from_response_db(self, response_db: np.ndarray) -> np.ndarray:
        residual = self.eq_target_db - response_db
        return fractional_octave_smoothing(self.freqs_hz, residual, fraction=10)

    def residual_db(
        self,
        bands: List["PEQBand"],
        response_builder: Callable[[np.ndarray, int, List["PEQBand"]], np.ndarray] | None = None,
    ) -> np.ndarray:
        builder = response_builder or peq_chain_response_db
        current = builder(self.freqs_hz, self.sample_rate, bands)
        return self.residual_from_response_db(current)

    def raw_residual_db(
        self,
        bands: List["PEQBand"],
        response_builder: Callable[[np.ndarray, int, List["PEQBand"]], np.ndarray] | None = None,
    ) -> np.ndarray:
        """Unsmoothed residual for bandwidth estimation."""
        builder = response_builder or peq_chain_response_db
        current = builder(self.freqs_hz, self.sample_rate, bands)
        return self.eq_target_db - current


@dataclass
class PEQBand:
    kind: Literal["peaking", "lowshelf", "highshelf"]
    freq: float
    gain_db: float
    q: float


@dataclass(frozen=True)
class GraphicEQProfile:
    name: str
    freqs_hz: tuple[float, ...]
    q: float


GRAPHIC_EQ_PROFILES: dict[str, GraphicEQProfile] = {
    "geq_10_band": GraphicEQProfile(
        name="geq_10_band",
        freqs_hz=(31.25, 62.5, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0),
        q=1.4142,
    ),
    "geq_31_band": GraphicEQProfile(
        name="geq_31_band",
        freqs_hz=(
            20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0,
            200.0, 250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0,
            2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0, 10000.0, 12500.0, 16000.0,
            20000.0,
        ),
        q=4.3185,
    ),
}


def _default_graphic_eq_profile_name(max_filters: int) -> str:
    if max_filters >= 31:
        return "geq_31_band"
    return "geq_10_band"


def graphic_eq_profile(name: str | None = None) -> GraphicEQProfile:
    resolved = name or "geq_10_band"
    try:
        return GRAPHIC_EQ_PROFILES[resolved]
    except KeyError as exc:
        raise ValueError(f"Unsupported GraphicEQ profile: {resolved}") from exc


def biquad_response_db(freqs_hz: np.ndarray, fs: int, band: PEQBand) -> np.ndarray:
    w0 = 2 * np.pi * band.freq / fs
    A = 10 ** (band.gain_db / 40)
    alpha = np.sin(w0) / (2 * max(band.q, 1e-6))
    cosw = np.cos(w0)

    if band.kind == "peaking":
        b0 = 1 + alpha * A
        b1 = -2 * cosw
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cosw
        a2 = 1 - alpha / A
    elif band.kind == "lowshelf":
        sqrtA = np.sqrt(A)
        S = max(0.1, min(1.0, band.q))
        alpha = np.sin(w0) / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
        b0 = A * ((A + 1) - (A - 1) * cosw + 2 * sqrtA * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cosw)
        b2 = A * ((A + 1) - (A - 1) * cosw - 2 * sqrtA * alpha)
        a0 = (A + 1) + (A - 1) * cosw + 2 * sqrtA * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cosw)
        a2 = (A + 1) + (A - 1) * cosw - 2 * sqrtA * alpha
    elif band.kind == "highshelf":
        sqrtA = np.sqrt(A)
        S = max(0.1, min(1.0, band.q))
        alpha = np.sin(w0) / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
        b0 = A * ((A + 1) + (A - 1) * cosw + 2 * sqrtA * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cosw)
        b2 = A * ((A + 1) + (A - 1) * cosw - 2 * sqrtA * alpha)
        a0 = (A + 1) - (A - 1) * cosw + 2 * sqrtA * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cosw)
        a2 = (A + 1) - (A - 1) * cosw - 2 * sqrtA * alpha
    else:
        raise ValueError(f"Unsupported band type: {band.kind}")

    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    _, h = signal.freqz(b, a, worN=2 * np.pi * freqs_hz / fs)
    return 20 * np.log10(np.maximum(np.abs(h), 1e-12))


def peq_chain_response_db(freqs_hz: np.ndarray, fs: int, bands: List[PEQBand]) -> np.ndarray:
    total = np.zeros_like(freqs_hz)
    for band in bands:
        total += biquad_response_db(freqs_hz, fs, band)
    return total


def graphic_eq_bands(profile: GraphicEQProfile, gains_db: np.ndarray | list[float]) -> list[PEQBand]:
    gains = list(gains_db)
    return [PEQBand("peaking", float(freq), float(gain), profile.q) for freq, gain in zip(profile.freqs_hz, gains)]


def fit_fixed_band_graphic_eq(
    freqs_hz: np.ndarray,
    target_eq_db: np.ndarray,
    sample_rate: int,
    *,
    budget: FilterBudget,
    max_gain_db: float = 12.0,
) -> list[PEQBand]:
    profile = graphic_eq_profile(budget.profile)
    objective = FitObjective.from_target(freqs_hz, target_eq_db, sample_rate)
    unit_columns = []
    for center_hz in profile.freqs_hz:
        unit_columns.append(biquad_response_db(freqs_hz, sample_rate, PEQBand("peaking", center_hz, 1.0, profile.q)))
    basis = np.column_stack(unit_columns)
    weighted_basis = basis * objective.weights[:, None]
    weighted_target = objective.eq_target_db * objective.weights
    gains, *_ = np.linalg.lstsq(weighted_basis, weighted_target, rcond=None)
    gains = np.clip(gains, -max_gain_db, max_gain_db)
    return graphic_eq_bands(profile, gains)


def _residual_priority_weights(freqs_hz: np.ndarray) -> np.ndarray:
    weights = np.ones_like(freqs_hz)
    weights[(freqs_hz >= 60) & (freqs_hz <= 10000)] = 1.5
    weights[(freqs_hz >= 2000) & (freqs_hz <= 8000)] = 2.0
    weights[freqs_hz > 12000] = 0.35
    return weights


def _band_mean(freqs_hz: np.ndarray, values_db: np.ndarray, low_hz: float, high_hz: float) -> float:
    mask = (freqs_hz >= low_hz) & (freqs_hz <= high_hz)
    if not np.any(mask):
        return 0.0
    return float(np.mean(values_db[mask]))


def _same_sign_fraction(values: np.ndarray, sign: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.mean(np.sign(values) == np.sign(sign)))


def _edge_shelf_candidate(freqs_hz: np.ndarray, eq_target: np.ndarray, *, kind: str, max_gain_db: float) -> PEQBand | None:
    if kind == "lowshelf":
        edge_mask = freqs_hz <= 140
        compare_mean = _band_mean(freqs_hz, eq_target, 180, 600)
        edge_mean = _band_mean(freqs_hz, eq_target, 20, 140)
        freq = 105.0
    else:
        edge_mask = freqs_hz >= 7000
        compare_mean = _band_mean(freqs_hz, eq_target, 2500, 5500)
        edge_mean = _band_mean(freqs_hz, eq_target, 7000, min(float(freqs_hz[-1]), 16000.0))
        freq = 8500.0

    if not np.any(edge_mask):
        return None
    edge_values = eq_target[edge_mask]
    if abs(edge_mean) < 1.25:
        return None
    if abs(edge_mean - compare_mean) < 0.75:
        return None
    if _same_sign_fraction(edge_values, edge_mean) < 0.7:
        return None
    return PEQBand(kind, freq, float(np.clip(edge_mean, -max_gain_db, max_gain_db)), 0.7)


def _max_q_for_frequency(freq_hz: float, requested_max_q: float) -> float:
    if freq_hz < 120:
        return min(requested_max_q, 2.0)
    if freq_hz > 6000:
        return min(requested_max_q, 3.0)
    return requested_max_q


def _nearby_same_sign_band_exists(bands: List[PEQBand], candidate: PEQBand) -> bool:
    for band in bands:
        if band.kind != candidate.kind:
            continue
        if np.sign(band.gain_db) != np.sign(candidate.gain_db):
            continue
        if abs(np.log2(max(band.freq, 1.0) / max(candidate.freq, 1.0))) < 0.2:
            return True
    return False


def _peaking_candidate(
    objective: FitObjective,
    residual: np.ndarray,
    idx: int,
    *,
    max_gain_db: float,
    max_q: float,
    raw_residual: np.ndarray | None = None,
) -> PEQBand:
    peak_db = float(residual[idx])
    fc = float(np.clip(objective.freqs_hz[idx], 35.0, objective.sample_rate / 2 - 500.0))

    # Use raw (unsmoothed) residual for bandwidth estimation when available,
    # so narrow features are not broadened by the 10th-octave smoother.
    bw_source = raw_residual if raw_residual is not None else residual
    threshold = abs(float(bw_source[idx])) * 0.5
    l = int(idx)
    while l > 0 and abs(bw_source[l]) >= threshold:
        l -= 1
    r = int(idx)
    while r < len(objective.freqs_hz) - 1 and abs(bw_source[r]) >= threshold:
        r += 1
    f1 = max(objective.freqs_hz[l], 20.0)
    f2 = min(objective.freqs_hz[r], objective.sample_rate / 2 - 100)
    bw_oct = max(np.log2(f2 / f1), 0.12)
    q_limit = _max_q_for_frequency(fc, max_q)
    q = float(np.clip(1.0 / bw_oct, 0.45, q_limit))
    gain = float(np.clip(peak_db, -max_gain_db, max_gain_db))
    if q >= 2.8:
        gain *= 0.85
    return PEQBand("peaking", fc, gain, q)


def _select_peaking_candidate(
    objective: FitObjective,
    residual: np.ndarray,
    bands: List[PEQBand],
    *,
    max_gain_db: float,
    max_q: float,
    min_peak_db: float,
    min_gain_db: float,
    allow_nearby_same_sign: bool,
) -> PEQBand | None:
    raw_residual = objective.raw_residual_db(bands)
    weighted = residual * objective.weights
    for idx in np.argsort(np.abs(weighted))[::-1]:
        peak_db = float(weighted[idx] / objective.weights[idx])
        if abs(peak_db) < min_peak_db:
            break
        candidate = _peaking_candidate(objective, residual, int(idx), max_gain_db=max_gain_db, max_q=max_q, raw_residual=raw_residual)
        if abs(candidate.gain_db) < min_gain_db:
            continue
        if not allow_nearby_same_sign and _nearby_same_sign_band_exists(bands, candidate):
            continue
        return candidate
    return None


def _refine_bands_jointly(
    objective: FitObjective,
    bands: List[PEQBand],
    *,
    max_gain_db: float,
    max_q: float,
) -> List[PEQBand]:
    """Joint Nelder-Mead refinement of peaking bands only. Shelves stay fixed."""
    from scipy.optimize import minimize

    peaking_indices = [i for i, b in enumerate(bands) if b.kind == 'peaking']
    if len(peaking_indices) < 2:
        return bands  # not enough peaking bands to justify refinement

    def _bands_from_params(params: np.ndarray) -> List[PEQBand]:
        result = list(bands)
        for pi, i in enumerate(peaking_indices):
            freq = float(np.clip(params[pi * 3], 25.0, objective.sample_rate / 2 - 200))
            gain = float(np.clip(params[pi * 3 + 1], -max_gain_db, max_gain_db))
            q = float(np.clip(params[pi * 3 + 2], 0.3, max_q))
            result[i] = PEQBand('peaking', freq, gain, q)
        return result

    def _cost(params: np.ndarray) -> float:
        trial = _bands_from_params(params)
        residual = objective.residual_db(trial)
        return float(np.sum((residual * objective.weights) ** 2))

    x0 = []
    for i in peaking_indices:
        x0.extend([bands[i].freq, bands[i].gain_db, bands[i].q])
    x0 = np.array(x0, dtype=np.float64)

    initial_cost = _cost(x0)
    max_iter = min(80 * len(peaking_indices), 400)
    result = minimize(_cost, x0, method='Nelder-Mead',
                      options={'maxiter': max_iter, 'xatol': 0.5, 'fatol': 0.05})

    if result.fun < initial_cost * 0.97:  # accept if >=3% improvement
        return _bands_from_params(result.x)
    return bands


def fit_peq(
    freqs_hz: np.ndarray,
    target_eq_db: np.ndarray,
    sample_rate: int,
    max_filters: int = 8,
    max_gain_db: float = 8.0,
    max_q: float = 4.5,
    *,
    budget: FilterBudget | None = None,
) -> List[PEQBand]:
    """Greedy fitter for PEQ and fixed-band GraphicEQ models."""
    budget = (budget or FilterBudget(max_filters=max_filters)).normalized()
    if budget.family == "graphic_eq":
        return fit_fixed_band_graphic_eq(
            freqs_hz,
            target_eq_db,
            sample_rate,
            budget=budget,
            max_gain_db=max_gain_db,
        )
    if budget.family != "peq":
        raise ValueError(f"Unsupported filter family: {budget.family}")

    objective = FitObjective.from_target(freqs_hz, target_eq_db, sample_rate)
    bands: List[PEQBand] = []

    shelf_candidates = [
        candidate
        for candidate in (
            _edge_shelf_candidate(freqs_hz, objective.eq_target_db, kind="lowshelf", max_gain_db=max_gain_db),
            _edge_shelf_candidate(freqs_hz, objective.eq_target_db, kind="highshelf", max_gain_db=max_gain_db),
        )
        if candidate is not None
    ]
    shelf_candidates.sort(key=lambda band: abs(band.gain_db), reverse=True)
    bands.extend(shelf_candidates[:budget.max_filters])

    while len(bands) < budget.max_filters:
        residual = objective.residual_db(bands)
        candidate = _select_peaking_candidate(
            objective,
            residual,
            bands,
            max_gain_db=max_gain_db,
            max_q=max_q,
            min_peak_db=0.75,
            min_gain_db=0.6,
            allow_nearby_same_sign=False,
        )
        if candidate is not None:
            bands.append(candidate)
            continue
        if budget.fill_policy != "exact_n":
            break

        candidate = _select_peaking_candidate(
            objective,
            residual,
            bands,
            max_gain_db=max_gain_db,
            max_q=max_q,
            min_peak_db=0.0,
            min_gain_db=0.0,
            allow_nearby_same_sign=False,
        )
        if candidate is None:
            candidate = _select_peaking_candidate(
                objective,
                residual,
                bands,
                max_gain_db=max_gain_db,
                max_q=max_q,
                min_peak_db=0.0,
                min_gain_db=0.0,
                allow_nearby_same_sign=True,
            )
        if candidate is None:
            break
        bands.append(candidate)


    # ── Joint refinement pass ─────────────────────────────────────────
    # After greedy placement, jointly refine all band parameters using
    # Nelder-Mead to reduce total weighted residual. This catches cases
    # where greedy placement left suboptimal parameter combinations.
    if len(bands) >= 2:
        bands = _refine_bands_jointly(objective, bands, max_gain_db=max_gain_db, max_q=max_q)
    return bands
