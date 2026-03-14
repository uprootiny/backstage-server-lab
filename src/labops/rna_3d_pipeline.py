"""
rna_3d_pipeline.py  —  RNA 3D Geometric Generative Pipeline  (v3 rewrite)
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, NamedTuple, Optional, Sequence

import numpy as np
import scipy.spatial.distance as spdist
from numpy.linalg import norm

NUCLEOTIDES: tuple[str, ...] = ("A", "U", "G", "C")
NT_IDX: dict[str, int] = {nt: i for i, nt in enumerate(NUCLEOTIDES)}
WC_COMPLEMENT: dict[str, str] = {"A": "U", "U": "A", "G": "C", "C": "G"}
GU_WOBBLE: dict[str, str] = {"G": "U", "U": "G"}
WC_PAIRS: frozenset = frozenset({frozenset({"A", "U"}), frozenset({"G", "C"})})
ALL_PAIRS: frozenset = WC_PAIRS | frozenset({frozenset({"G", "U"})})


def can_pair(a: str, b: str, *, wobble: bool = True) -> bool:
    return frozenset({a, b}) in (ALL_PAIRS if wobble else WC_PAIRS)


def pair_type(a: str, b: str) -> str:
    p = frozenset({a, b})
    if p in WC_PAIRS:
        return "WC"
    if p in ALL_PAIRS:
        return "GU"
    return "none"


def normalize(v: np.ndarray, tol: float = 1e-12) -> np.ndarray:
    n = float(norm(v))
    return v / n if n > tol else v


def rodrigues(axis: np.ndarray, theta: float) -> np.ndarray:
    k = normalize(axis)
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)


def dihedral_angle(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    b1 = normalize(p1 - p0)
    b2 = normalize(p2 - p1)
    b3 = normalize(p3 - p2)
    n1 = normalize(np.cross(b1, b2))
    n2 = normalize(np.cross(b2, b3))
    m1 = np.cross(n1, b2)
    return math.degrees(math.atan2(float(m1 @ n2), float(n1 @ n2)))


@dataclass(frozen=True)
class GrammarConfig:
    stem_min: int = 3
    stem_max: int = 12
    loop_min: int = 3
    loop_max: int = 8
    iloop_min: int = 2
    iloop_max: int = 5
    bulge_min: int = 1
    bulge_max: int = 3
    gc_bias: float = 0.52
    wobble_p: float = 0.12
    max_depth: int = 6
    p_iloop: float = 0.40
    p_bulge: float = 0.25

    def __post_init__(self) -> None:
        assert 0 < self.stem_min <= self.stem_max
        assert 3 <= self.loop_min <= self.loop_max
        assert 0 < self.bulge_min <= self.bulge_max
        assert self.p_iloop >= 0 and self.p_bulge >= 0 and self.p_iloop + self.p_bulge < 1.0
        assert 0.0 <= self.gc_bias <= 1.0
        assert 0.0 <= self.wobble_p <= 1.0
        assert self.max_depth >= 1


DEFAULT_CFG = GrammarConfig()


@dataclass(frozen=True)
class Motif:
    sequence: str
    bracket: str
    kind: str
    pairs: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if len(self.sequence) != len(self.bracket):
            raise ValueError("sequence/bracket length mismatch")
        n = len(self.sequence)
        for i, j in self.pairs:
            if not (0 <= i < j < n):
                raise ValueError(f"invalid pair ({i},{j})")

    @property
    def n(self) -> int:
        return len(self.sequence)


def _sample_nt_stem(rng: np.random.Generator, gc_bias: float) -> str:
    p = np.array([(1.0 - gc_bias) / 2.0, (1.0 - gc_bias) / 2.0, gc_bias / 2.0, gc_bias / 2.0])
    return NUCLEOTIDES[rng.choice(4, p=p)]


def _sample_nt_loop(rng: np.random.Generator) -> str:
    return NUCLEOTIDES[rng.integers(4)]


def _sample_stem_pair(rng: np.random.Generator, cfg: GrammarConfig) -> tuple[str, str]:
    nt5 = _sample_nt_stem(rng, cfg.gc_bias)
    nt3 = GU_WOBBLE[nt5] if nt5 in GU_WOBBLE and rng.random() < cfg.wobble_p else WC_COMPLEMENT[nt5]
    return nt5, nt3


def _randint(rng: np.random.Generator, lo: int, hi: int) -> int:
    return int(rng.integers(lo, hi + 1))


def _wrap_in_stem(rng: np.random.Generator, cfg: GrammarConfig, inner: Motif, s_len: int, offset5: int = 0, offset3: int = 0) -> Motif:
    pairs5, pairs3 = zip(*[_sample_stem_pair(rng, cfg) for _ in range(s_len)])
    flank5 = "".join(_sample_nt_loop(rng) for _ in range(offset5))
    flank3 = "".join(_sample_nt_loop(rng) for _ in range(offset3))
    seq = "".join(pairs5) + flank5 + inner.sequence + flank3 + "".join(reversed(pairs3))
    brk = "(" * s_len + "." * offset5 + inner.bracket + "." * offset3 + ")" * s_len
    stem_bp = tuple((i, len(seq) - 1 - i) for i in range(s_len))
    inner_off = s_len + offset5
    inner_bp = tuple((i + inner_off, j + inner_off) for i, j in inner.pairs)
    return Motif(seq, brk, "stem", tuple(sorted(stem_bp + inner_bp)))


def make_hairpin(rng: np.random.Generator, cfg: GrammarConfig = DEFAULT_CFG) -> Motif:
    s_len = _randint(rng, cfg.stem_min, cfg.stem_max)
    l_len = _randint(rng, cfg.loop_min, cfg.loop_max)
    p5, p3 = zip(*[_sample_stem_pair(rng, cfg) for _ in range(s_len)])
    loop = "".join(_sample_nt_loop(rng) for _ in range(l_len))
    seq = "".join(p5) + loop + "".join(reversed(p3))
    brk = "(" * s_len + "." * l_len + ")" * s_len
    pairs = tuple((i, len(seq) - 1 - i) for i in range(s_len))
    return Motif(seq, brk, "hairpin", pairs)


def make_internal_loop(rng: np.random.Generator, cfg: GrammarConfig, inner: Motif) -> Motif:
    s_len = _randint(rng, cfg.stem_min, min(cfg.stem_min + 3, cfg.stem_max))
    l5 = _randint(rng, cfg.iloop_min, cfg.iloop_max)
    l3 = _randint(rng, cfg.iloop_min, cfg.iloop_max)
    return _wrap_in_stem(rng, cfg, inner, s_len, offset5=l5, offset3=l3)


def make_bulge(rng: np.random.Generator, cfg: GrammarConfig, inner: Motif) -> Motif:
    s_len = _randint(rng, cfg.stem_min, min(cfg.stem_min + 3, cfg.stem_max))
    b_len = _randint(rng, cfg.bulge_min, cfg.bulge_max)
    return _wrap_in_stem(rng, cfg, inner, s_len, offset5=b_len, offset3=0)


def derive(rng: np.random.Generator, cfg: GrammarConfig = DEFAULT_CFG, depth: int = 0) -> Motif:
    if depth >= cfg.max_depth:
        return make_hairpin(rng, cfg)
    r = rng.random()
    if r < cfg.p_iloop:
        return make_internal_loop(rng, cfg, derive(rng, cfg, depth + 1))
    if r < cfg.p_iloop + cfg.p_bulge:
        return make_bulge(rng, cfg, derive(rng, cfg, depth + 1))
    return make_hairpin(rng, cfg)


MIN_HAIRPIN_LOOP = 3


def nussinov(seq: str, min_loop: int = MIN_HAIRPIN_LOOP) -> tuple[np.ndarray, list[tuple[int, int]]]:
    n = len(seq)
    dp = np.zeros((n, n), dtype=np.int32)
    for span in range(min_loop + 1, n):
        for i in range(n - span):
            j = i + span
            best = int(dp[i, j - 1])
            for k in range(i, j):
                v = int(dp[i, k]) + int(dp[k + 1, j])
                if v > best:
                    best = v
            if can_pair(seq[i], seq[j]) and (j - i - 1) >= min_loop:
                inner = int(dp[i + 1, j - 1]) if i + 1 <= j - 1 else 0
                best = max(best, inner + 1)
            dp[i, j] = best

    pairs: list[tuple[int, int]] = []

    def _trace(i: int, j: int) -> None:
        if i >= j:
            return
        if dp[i, j] == dp[i, j - 1]:
            _trace(i, j - 1)
            return
        for k in range(i, j):
            if dp[i, j] == int(dp[i, k]) + int(dp[k + 1, j]):
                _trace(i, k)
                _trace(k + 1, j)
                return
        if can_pair(seq[i], seq[j]) and (j - i - 1) >= min_loop:
            inner = int(dp[i + 1, j - 1]) if i + 1 <= j - 1 else 0
            if dp[i, j] == inner + 1:
                pairs.append((i, j))
                _trace(i + 1, j - 1)
                return
        _trace(i, j - 1)

    _trace(0, n - 1)
    pairs.sort()
    return dp, pairs


def pairs_to_bracket(n: int, pairs: Sequence[tuple[int, int]]) -> str:
    arr = ["."] * n
    for i, j in pairs:
        arr[i] = "("
        arr[j] = ")"
    return "".join(arr)


LOOP_LABELS = ("stem", "hairpin", "internal", "bulge", "free")
LOOP_LABEL_IDX = {lbl: i for i, lbl in enumerate(LOOP_LABELS)}


def label_loop_types(bracket: str, pairs: Sequence[tuple[int, int]]) -> list[str]:
    n = len(bracket)
    lbl = ["free"] * n
    pm = dict(list(pairs) + [(j, i) for i, j in pairs])
    for i, j in pairs:
        lbl[i] = lbl[j] = "stem"
    i = 0
    while i < n:
        if bracket[i] != ".":
            i += 1
            continue
        j = i
        while j < n and bracket[j] == ".":
            j += 1
        left = next((k for k in range(i - 1, -1, -1) if bracket[k] == "("), None)
        right = next((k for k in range(j, n) if bracket[k] == ")"), None)
        if left is None or right is None:
            kind = "free"
        elif pm.get(left) == right:
            kind = "hairpin"
        else:
            partner = pm.get(left)
            kind = "internal" if partner is not None and partner > right else "bulge"
        for k in range(i, j):
            lbl[k] = kind
        i = j
    return lbl


class StructuralStats(NamedTuple):
    n: int
    n_pairs: int
    n_paired: int
    pairing_fraction: float
    max_nesting_depth: int
    max_pair_span: int


def structural_stats(seq: str, pairs: Sequence[tuple[int, int]]) -> StructuralStats:
    n = len(seq)
    paired = {i for p in pairs for i in p}
    brk = pairs_to_bracket(n, pairs)
    depth = 0
    depths: list[int] = []
    for ch in brk:
        if ch == "(":
            depth += 1
        depths.append(depth)
        if ch == ")":
            depth -= 1
    return StructuralStats(
        n=n,
        n_pairs=len(pairs),
        n_paired=len(paired),
        pairing_fraction=len(paired) / n if n else 0.0,
        max_nesting_depth=max(depths, default=0),
        max_pair_span=max((j - i for i, j in pairs), default=0),
    )


@dataclass(frozen=True)
class SecondaryRecord:
    motif: Motif
    dp: np.ndarray
    pairs: list[tuple[int, int]]
    bracket: str
    labels: list[str]
    stats: StructuralStats


def fold_motif(motif: Motif) -> SecondaryRecord:
    dp, pairs = nussinov(motif.sequence)
    bracket = pairs_to_bracket(motif.n, pairs)
    labels = label_loop_types(bracket, pairs)
    stats = structural_stats(motif.sequence, pairs)
    return SecondaryRecord(motif=motif, dp=dp, pairs=pairs, bracket=bracket, labels=labels, stats=stats)


@dataclass(frozen=True)
class AFormParams:
    rise: float = 2.81
    twist: float = math.radians(32.7)
    radius: float = 9.0


AFORM = AFormParams()
LOOP_BOND = 5.9


@dataclass
class SE3Frame:
    pos: np.ndarray
    T: np.ndarray
    N: np.ndarray

    def __post_init__(self) -> None:
        self.T = normalize(self.T)
        self.N = normalize(self.N - self.T * float(self.T @ self.N))

    @property
    def B(self) -> np.ndarray:
        return np.cross(self.T, self.N)

    @property
    def R(self) -> np.ndarray:
        return np.column_stack([self.N, self.B, self.T])

    def apply(self, local_pt: np.ndarray) -> np.ndarray:
        return self.pos + self.R @ local_pt

    @classmethod
    def identity(cls) -> "SE3Frame":
        return cls(pos=np.zeros(3), T=np.array([0.0, 0.0, 1.0]), N=np.array([1.0, 0.0, 0.0]))


def bishop_transport(T_curr: np.ndarray, T_next: np.ndarray, N_curr: np.ndarray) -> np.ndarray:
    axis = np.cross(T_curr, T_next)
    sin_a = float(norm(axis))
    cos_a = float(np.clip(T_curr @ T_next, -1.0, 1.0))
    if sin_a < 1e-12:
        if cos_a > 0.0:
            N_next = N_curr.copy()
        else:
            perp = np.array([1.0, 0.0, 0.0]) if abs(T_curr[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            ax180 = normalize(np.cross(T_curr, perp))
            N_next = rodrigues(ax180, math.pi) @ N_curr
    else:
        N_next = rodrigues(axis / sin_a, math.atan2(sin_a, cos_a)) @ N_curr
    N_next -= T_next * float(T_next @ N_next)
    return normalize(N_next)


def helix_coords(n_residues: int, frame: SE3Frame, p: AFormParams = AFORM, phi0: float = 0.0) -> tuple[np.ndarray, SE3Frame, float]:
    r, h, w = p.radius, p.rise, p.twist
    coords = np.empty((n_residues, 3))
    for k in range(n_residues):
        phi = phi0 + k * w
        local = np.array([r * math.cos(phi), r * math.sin(phi), k * h])
        coords[k] = frame.apply(local)
    end_phi = phi0 + n_residues * w
    dphi = 1e-5
    p_exit = np.array([r * math.cos(end_phi), r * math.sin(end_phi), n_residues * h])
    p_next = np.array([r * math.cos(end_phi + dphi), r * math.sin(end_phi + dphi), n_residues * h + h * dphi / w])
    end_pos = frame.apply(p_exit)
    T_new = normalize(frame.apply(p_next) - end_pos)
    N_new = bishop_transport(frame.T, T_new, frame.N)
    return coords, SE3Frame(end_pos, T_new, N_new), end_phi


def loop_coords(n_residues: int, frame: SE3Frame, bond_len: float = LOOP_BOND, kappa_mean: float = 0.04, tau_std: float = 0.08, rng: Optional[np.random.Generator] = None) -> tuple[np.ndarray, SE3Frame]:
    if rng is None:
        rng = np.random.default_rng()
    coords = np.empty((n_residues, 3))
    T, N = frame.T.copy(), frame.N.copy()
    pos = frame.pos.copy()
    for k in range(n_residues):
        coords[k] = pos
        B = np.cross(T, N)
        kappa = abs(float(rng.normal(kappa_mean, kappa_mean * 0.5)))
        tau = float(rng.normal(0.0, tau_std))
        T_new = normalize(T + kappa * bond_len * N + tau * bond_len * B)
        N_new = bishop_transport(T, T_new, N)
        pos += bond_len * T
        T, N = T_new, N_new
    return coords, SE3Frame(pos, T, N)


def _scan_segments(bracket: str) -> list[tuple[str, int, int]]:
    n, i = len(bracket), 0
    segs: list[tuple[str, int, int]] = []
    while i < n:
        ch = bracket[i]
        j = i
        if ch == "(":
            while j < n and bracket[j] == "(":
                j += 1
            segs.append(("stem_open", i, j))
        elif ch == ")":
            while j < n and bracket[j] == ")":
                j += 1
            segs.append(("stem_close", i, j))
        else:
            while j < n and bracket[j] == ".":
                j += 1
            segs.append(("loop", i, j))
        i = j
    return segs


def bracket_to_3d(bracket: str, rng: Optional[np.random.Generator] = None, noise: float = 0.2) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng()
    n = len(bracket)
    coords = np.empty((n, 3))
    frame = SE3Frame.identity()
    phi0 = 0.0
    for kind, i, j in _scan_segments(bracket):
        n_seg = j - i
        if kind in ("stem_open", "stem_close"):
            seg_coords, frame, phi0 = helix_coords(n_seg, frame, phi0=phi0)
        else:
            seg_coords, frame = loop_coords(n_seg, frame, rng=rng)
        coords[i:j] = seg_coords
    coords += rng.normal(0.0, noise, coords.shape)
    return coords


def compute_dihedrals(coords: np.ndarray) -> np.ndarray:
    n = len(coords)
    d = np.full(n, np.nan)
    for i in range(1, n - 2):
        d[i] = dihedral_angle(coords[i - 1], coords[i], coords[i + 1], coords[i + 2])
    return d


@dataclass(frozen=True)
class GeometryRecord:
    coords: np.ndarray
    dihedrals: np.ndarray


def build_geometry(sr: SecondaryRecord, rng: Optional[np.random.Generator] = None) -> GeometryRecord:
    if rng is None:
        rng = np.random.default_rng(seed=hash(sr.bracket) % (2**31))
    coords = bracket_to_3d(sr.bracket, rng=rng)
    dihedrals = compute_dihedrals(coords)
    return GeometryRecord(coords=coords, dihedrals=dihedrals)


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n
        self.birth = [0.0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int, w: float) -> Optional[tuple[float, float]]:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return None
        if self.birth[rx] <= self.birth[ry]:
            older, younger = rx, ry
        else:
            older, younger = ry, rx
        killed = (self.birth[younger], w)
        if self.rank[older] >= self.rank[younger]:
            self.parent[younger] = older
            if self.rank[older] == self.rank[younger]:
                self.rank[older] += 1
        else:
            self.parent[older] = younger
            self.birth[younger] = self.birth[older]
        return killed


@dataclass(frozen=True)
class PersistenceDiagram:
    H0: tuple[tuple[float, float], ...]
    H1: tuple[tuple[float, float], ...]
    max_filtration: float


def pairwise_dist(coords: np.ndarray) -> np.ndarray:
    return spdist.cdist(coords, coords, metric="euclidean")


def vietoris_rips(D: np.ndarray, max_rad: Optional[float] = None) -> PersistenceDiagram:
    n = D.shape[0]
    cap = float(D.max()) if max_rad is None else float(max_rad)
    edges = sorted((float(D[i, j]), i, j) for i in range(n) for j in range(i + 1, n) if D[i, j] <= cap)
    uf = UnionFind(n)
    H0: list[tuple[float, float]] = []
    H1: list[tuple[float, float]] = []
    adj: dict[int, set[int]] = defaultdict(set)
    for w, i, j in edges:
        killed = uf.union(i, j, w)
        if killed is not None:
            b, d = killed
            if d > b:
                H0.append((b, d))
        else:
            common = adj[i] & adj[j]
            if common:
                k = min(common, key=lambda v: max(float(D[i, v]), float(D[j, v])))
                death = max(w, float(D[i, k]), float(D[j, k]))
            else:
                death = cap
            if death > w:
                H1.append((w, death))
        adj[i].add(j)
        adj[j].add(i)
    seen: set[int] = set()
    for v in range(n):
        r = uf.find(v)
        if r not in seen:
            seen.add(r)
            H0.append((uf.birth[r], cap))
    return PersistenceDiagram(H0=tuple(H0), H1=tuple(H1), max_filtration=cap)


def betti_curve(diagram: Sequence[tuple[float, float]], t: np.ndarray) -> np.ndarray:
    if not diagram:
        return np.zeros(len(t), dtype=np.int32)
    b = np.fromiter((x[0] for x in diagram), dtype=np.float64, count=len(diagram))
    d = np.fromiter((x[1] for x in diagram), dtype=np.float64, count=len(diagram))
    return ((t[:, None] >= b[None, :]) & (t[:, None] < d[None, :])).sum(axis=1).astype(np.int32)


TDA_DIM = 48
_TDA_N_BINS = 20


def _persistence_stats(diagram: Sequence[tuple[float, float]]) -> np.ndarray:
    p = np.array([d - b for b, d in diagram if d > b], dtype=np.float64)
    if len(p) == 0:
        return np.zeros(4, dtype=np.float64)
    return np.array([p.mean(), p.std(), p.max(), float(len(p))], dtype=np.float64)


def topo_features(dgm: PersistenceDiagram) -> np.ndarray:
    t = np.linspace(0.0, dgm.max_filtration + 1e-6, _TDA_N_BINS)
    feat = np.concatenate([
        _persistence_stats(dgm.H0),
        _persistence_stats(dgm.H1),
        betti_curve(dgm.H0, t).astype(np.float64),
        betti_curve(dgm.H1, t).astype(np.float64),
    ])
    assert feat.shape[0] == TDA_DIM
    return feat


@dataclass(frozen=True)
class TDARecord:
    D: np.ndarray
    dgm: PersistenceDiagram
    feat: np.ndarray


def build_tda(gr: GeometryRecord) -> TDARecord:
    D = pairwise_dist(gr.coords)
    dgm = vietoris_rips(D)
    feat = topo_features(dgm)
    return TDARecord(D=D, dgm=dgm, feat=feat)


EDGE_TYPE_IDX: dict[str, int] = {"backbone": 0, "WC": 1, "GU": 2, "stacking": 3}
NODE_DIM: int = 16
EDGE_DIM: int = 9


@dataclass(frozen=True)
class MolecularGraph:
    node_feats: np.ndarray
    edge_index: np.ndarray
    edge_feats: np.ndarray
    coords: np.ndarray


def build_graph(sr: SecondaryRecord, gr: GeometryRecord, tda: TDARecord, spatial_cutoff: float = 15.0) -> MolecularGraph:
    seq = sr.motif.sequence
    bracket = sr.bracket
    pairs = sr.pairs
    labels = sr.labels
    coords = gr.coords
    D = tda.D
    topo = tda.feat
    n = len(seq)
    pm = dict(list(pairs) + [(j, i) for i, j in pairs])

    c0 = coords - coords.mean(axis=0)
    scale = math.sqrt(float((c0**2).sum(axis=1).max())) + 1e-6
    c0 = (c0 / scale).astype(np.float32)

    topo_n = topo / (np.abs(topo).max() + 1e-6)
    topo4 = topo_n[:4].astype(np.float32)
    topo_h1 = topo_n[4:8].astype(np.float32)

    nf = np.zeros((n, NODE_DIM), dtype=np.float32)
    for i, (nt, lb) in enumerate(zip(seq, labels)):
        nf[i, NT_IDX[nt]] = 1.0
        nf[i, 4 + LOOP_LABEL_IDX.get(lb, 4)] = 1.0
        nf[i, 9:12] = c0[i]
        nf[i, 12:16] = topo4

    src_list: list[int] = []
    dst_list: list[int] = []
    ef_list: list[np.ndarray] = []

    def _add_edge(i: int, j: int, etype: str) -> None:
        feat = np.zeros(EDGE_DIM, dtype=np.float32)
        feat[EDGE_TYPE_IDX[etype]] = 1.0
        feat[4] = float(D[i, j]) / spatial_cutoff
        feat[5:] = topo_h1
        for s, t in ((i, j), (j, i)):
            src_list.append(s)
            dst_list.append(t)
            ef_list.append(feat)

    for i in range(n):
        if i < n - 1:
            _add_edge(i, i + 1, "backbone")
        if i in pm and pm[i] > i:
            j = pm[i]
            ety = "WC" if pair_type(seq[i], seq[j]) == "WC" else "GU"
            _add_edge(i, j, ety)
        for j in range(i + 2, min(i + 8, n)):
            if float(D[i, j]) < spatial_cutoff and bracket[i] != "." and bracket[j] != ".":
                _add_edge(i, j, "stacking")

    edge_index = np.array([src_list, dst_list], dtype=np.int32)
    edge_feats = np.stack(ef_list) if ef_list else np.zeros((0, EDGE_DIM), dtype=np.float32)
    return MolecularGraph(node_feats=nf, edge_index=edge_index, edge_feats=edge_feats, coords=c0)


def silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    mu = x.mean(axis=-1, keepdims=True)
    sigma = x.std(axis=-1, keepdims=True)
    return (x - mu) / (sigma + eps)


@dataclass
class MLP:
    W: list[np.ndarray]
    b: list[np.ndarray]
    act: Callable[[np.ndarray], np.ndarray] = field(default=silu, compare=False)

    @classmethod
    def make(cls, dims: list[int], act: Callable[[np.ndarray], np.ndarray] = silu, rng: Optional[np.random.Generator] = None) -> "MLP":
        if rng is None:
            rng = np.random.default_rng()
        W, b = [], []
        for d_in, d_out in zip(dims[:-1], dims[1:]):
            scale = math.sqrt(6.0 / (d_in + d_out))
            W.append(rng.uniform(-scale, scale, (d_out, d_in)).astype(np.float32))
            b.append(np.zeros(d_out, dtype=np.float32))
        return cls(W=W, b=b, act=act)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        for i, (w, bi) in enumerate(zip(self.W, self.b)):
            x = x @ w.T + bi
            if i < len(self.W) - 1:
                x = self.act(x)
        return x


@dataclass
class EGNNLayer:
    phi_e: MLP
    phi_h: MLP
    phi_x: MLP

    @classmethod
    def make(cls, d_h: int, d_e: int, d_msg: int, rng: Optional[np.random.Generator] = None) -> "EGNNLayer":
        if rng is None:
            rng = np.random.default_rng()
        return cls(
            phi_e=MLP.make([2 * d_h + 1 + d_e, d_msg, d_msg], rng=rng),
            phi_h=MLP.make([d_h + d_msg, d_h, d_h], rng=rng),
            phi_x=MLP.make([d_msg, 1], rng=rng),
        )

    def forward(self, h: np.ndarray, x: np.ndarray, edge_index: np.ndarray, edge_attr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = h.shape[0]
        src_idx = edge_index[0]
        dst_idx = edge_index[1]
        diff = x[src_idx] - x[dst_idx]
        sq_dist = (diff**2).sum(axis=-1, keepdims=True)
        msg = self.phi_e(np.concatenate([h[src_idx], h[dst_idx], sq_dist, edge_attr], axis=-1))
        count = np.bincount(dst_idx, minlength=n).clip(min=1).astype(np.float32)[:, None]
        agg = np.zeros((n, msg.shape[1]), dtype=np.float32)
        np.add.at(agg, dst_idx, msg)
        agg /= count
        h_new = layer_norm(h + self.phi_h(np.concatenate([h, agg], axis=-1)))
        weights = self.phi_x(msg)
        coord_upd = np.zeros((n, 3), dtype=np.float32)
        np.add.at(coord_upd, src_idx, diff * weights)
        coord_upd /= count
        x_new = x + coord_upd
        return h_new, x_new


class EGNNOutput(NamedTuple):
    graph_embed: np.ndarray
    node_embed: np.ndarray
    refined_coords: np.ndarray
    pred_pf: float
    pred_nd: float


@dataclass
class EGNNModel:
    encoder: MLP
    layers: list[EGNNLayer]
    readout: MLP

    @classmethod
    def make(cls, d_in: int = NODE_DIM, d_h: int = 64, d_e: int = EDGE_DIM, d_msg: int = 32, n_layers: int = 4, rng: Optional[np.random.Generator] = None) -> "EGNNModel":
        if rng is None:
            rng = np.random.default_rng()
        return cls(
            encoder=MLP.make([d_in, d_h, d_h], rng=rng),
            layers=[EGNNLayer.make(d_h, d_e, d_msg, rng=rng) for _ in range(n_layers)],
            readout=MLP.make([d_h, d_h // 2, 2], rng=rng),
        )

    def forward(self, g: MolecularGraph) -> EGNNOutput:
        h = self.encoder(g.node_feats)
        x = g.coords.copy()
        for layer in self.layers:
            h, x = layer.forward(h, x, g.edge_index, g.edge_feats)
        graph_embed = h.mean(axis=0)
        pred = self.readout(graph_embed[None])[0]
        pred_pf = float(1.0 / (1.0 + np.exp(-float(np.clip(pred[0], -30, 30)))))
        pred_nd = float(np.exp(float(np.clip(pred[1], -10, 10))))
        return EGNNOutput(graph_embed=graph_embed, node_embed=h, refined_coords=x, pred_pf=pred_pf, pred_nd=pred_nd)


@dataclass(frozen=True)
class MoleculeRecord:
    secondary: SecondaryRecord
    geometry: GeometryRecord
    tda: TDARecord
    graph: MolecularGraph


def build_record(motif: Motif, spatial_cutoff: float = 15.0) -> MoleculeRecord:
    sr = fold_motif(motif)
    gr = build_geometry(sr)
    tda = build_tda(gr)
    g = build_graph(sr, gr, tda, spatial_cutoff=spatial_cutoff)
    return MoleculeRecord(secondary=sr, geometry=gr, tda=tda, graph=g)


def build_tda(gr: GeometryRecord) -> TDARecord:
    D = pairwise_dist(gr.coords)
    dgm = vietoris_rips(D)
    feat = topo_features(dgm)
    return TDARecord(D=D, dgm=dgm, feat=feat)


def export_dataset(records: list[MoleculeRecord], out_path: str) -> None:
    N = len(records)
    max_n = max(r.graph.node_feats.shape[0] for r in records)
    node_arr = np.zeros((N, max_n, NODE_DIM), dtype=np.float32)
    mask_arr = np.zeros((N, max_n), dtype=bool)
    topo_arr = np.stack([r.tda.feat for r in records]).astype(np.float64)
    label_pf = np.array([r.secondary.stats.pairing_fraction for r in records], dtype=np.float32)
    label_nd = np.array([r.secondary.stats.max_nesting_depth for r in records], dtype=np.int32)
    gc_arr = np.array([
        sum(c in "GC" for c in r.secondary.motif.sequence) / r.secondary.motif.n for r in records
    ], dtype=np.float32)
    for k, r in enumerate(records):
        ln = r.graph.node_feats.shape[0]
        node_arr[k, :ln] = r.graph.node_feats
        mask_arr[k, :ln] = True
    np.savez_compressed(out_path, node_features=node_arr, attention_mask=mask_arr, topo_features=topo_arr, label_pf=label_pf, label_nd=label_nd, gc_bias=gc_arr)


if __name__ == "__main__":
    N_SAMPLES = 64
    rng = np.random.default_rng(seed=42)
    cfg = GrammarConfig()
    corpus = [derive(rng, cfg) for _ in range(N_SAMPLES)]
    records = [build_record(m) for m in corpus]
    model = EGNNModel.make(rng=rng)
    ex = records[3]
    out = model.forward(ex.graph)
    print(f"Generated {N_SAMPLES} molecules")
    print(f"EGNN forward pass ✓ pred_pf={out.pred_pf:.4f} true={ex.secondary.stats.pairing_fraction:.4f}")
    export_dataset(records, "/tmp/rna_corpus_v3.npz")
    print("Saved /tmp/rna_corpus_v3.npz")
