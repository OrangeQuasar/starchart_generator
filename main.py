"""星図生成コアライブラリ / Star Chart Generator core library"""

import csv
import gzip
import io
import json
import math
import pickle
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np
from astropy import units as u
from astropy.coordinates import (
    AltAz, EarthLocation, SkyCoord,
    get_body, solar_system_ephemeris,
)
from astropy.time import Time

# ─── Data cache ────────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".seizu"
HYG_CACHE = DATA_DIR / "hyg.pkl"
CONST_CACHE = DATA_DIR / "constellations.pkl"

HYG_URLS: list[tuple[str, bool]] = [
    ("https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/CURRENT/hygdata_v41.csv", False),
    ("https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/CURRENT/hygdata_v40.csv.gz", True),
    ("https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/v3/hyg_v38.csv.gz", True),
]
CONST_URL = (
    "https://raw.githubusercontent.com/Stellarium/stellarium"
    "/master/skycultures/modern/index.json"
)

# ─── Planet definitions ─────────────────────────────────────────────────────────

PLANETS = ["moon", "mercury", "venus", "mars", "jupiter", "saturn"]

PLANET_NAMES: dict[str, dict[str, str]] = {
    "ja": {
        "moon": "月", "mercury": "水星", "venus": "金星", "mars": "火星",
        "jupiter": "木星", "saturn": "土星", "uranus": "天王星", "neptune": "海王星",
    },
    "en": {
        "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars",
        "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
    },
}

PLANET_COLORS: dict[str, str] = {
    "moon": "#ffffcc", "mercury": "#bbbbbb", "venus": "#ffffaa",
    "mars": "#ff8866", "jupiter": "#ffd8a8", "saturn": "#ffe88a",
    "uranus": "#99ddff", "neptune": "#6688ff",
}

# ─── 8 cardinal directions ──────────────────────────────────────────────────────

DIRECTIONS_8 = [
    ("N",  0,   "北"),
    ("NE", 45,  "北東"),
    ("E",  90,  "東"),
    ("SE", 135, "南東"),
    ("S",  180, "南"),
    ("SW", 225, "南西"),
    ("W",  270, "西"),
    ("NW", 315, "北西"),
]

DIRECTION_TO_AZ: dict[str, float] = {
    "北": 0, "北東": 45, "東": 90, "南東": 135,
    "南": 180, "南西": 225, "西": 270, "北西": 315,
    "N": 0, "NE": 45, "E": 90, "SE": 135,
    "S": 180, "SW": 225, "W": 270, "NW": 315,
}

# ─── Constellation names ────────────────────────────────────────────────────────

CONSTELLATION_NAMES: dict[str, dict[str, str]] = {
    "ja": {
        "And": "アンドロメダ", "Ant": "ポンプ", "Aps": "ふうちょう",
        "Aqr": "みずがめ", "Aql": "わし", "Ara": "さいだん",
        "Ari": "おひつじ", "Aur": "ぎょしゃ", "Boo": "うしかい",
        "Cae": "ちょうこくき", "Cam": "きりん", "Cnc": "かに",
        "CVn": "りょうけん", "CMa": "おおいぬ", "CMi": "こいぬ",
        "Cap": "やぎ", "Car": "りゅうこつ", "Cas": "カシオペア",
        "Cen": "ケンタウルス", "Cep": "ケフェウス", "Cet": "くじら",
        "Cha": "カメレオン", "Cir": "コンパス", "Col": "はと",
        "Com": "かみのけ", "CrA": "みなみかんむり", "CrB": "かんむり",
        "Crv": "からす", "Crt": "コップ", "Cru": "みなみじゅうじ",
        "Cyg": "はくちょう", "Del": "いるか", "Dor": "かじき",
        "Dra": "りゅう", "Equ": "こうま", "Eri": "エリダヌス",
        "For": "ろ", "Gem": "ふたご", "Gru": "つる",
        "Her": "ヘルクレス", "Hor": "とけい", "Hya": "うみへび",
        "Hyi": "みずへび", "Ind": "インディアン", "Lac": "とかげ",
        "Leo": "しし", "LMi": "こじし", "Lep": "うさぎ",
        "Lib": "てんびん", "Lup": "おおかみ", "Lyn": "やまねこ",
        "Lyr": "こと", "Men": "テーブルさん", "Mic": "けんびきょう",
        "Mon": "いっかくじゅう", "Mus": "はえ", "Nor": "じょうぎ",
        "Oct": "はちぶんぎ", "Oph": "へびつかい", "Ori": "オリオン",
        "Pav": "くじゃく", "Peg": "ペガスス", "Per": "ペルセウス",
        "Phe": "ほうおう", "Pic": "がか", "Psc": "うお",
        "PsA": "みなみのうお", "Pup": "とも", "Pyx": "らしんばん",
        "Ret": "レチクル", "Sge": "や", "Sgr": "いて",
        "Sco": "さそり", "Scl": "ちょうこくしつ", "Sct": "たて",
        "Ser": "へび", "Sex": "ろくぶんぎ", "Tau": "おうし",
        "Tel": "ぼうえんきょう", "TrA": "みなみさんかく", "Tri": "さんかく",
        "Tuc": "きょしちょう", "UMa": "おおぐま", "UMi": "こぐま",
        "Vel": "ほ座", "Vir": "おとめ", "Vol": "とびうお",
        "Vul": "こぎつね",
    },
    "en": {
        "And": "Andromeda", "Ant": "Antlia", "Aps": "Apus",
        "Aqr": "Aquarius", "Aql": "Aquila", "Ara": "Ara",
        "Ari": "Aries", "Aur": "Auriga", "Boo": "Boötes",
        "Cae": "Caelum", "Cam": "Camelopardalis", "Cnc": "Cancer",
        "CVn": "Canes Venatici", "CMa": "Canis Major", "CMi": "Canis Minor",
        "Cap": "Capricornus", "Car": "Carina", "Cas": "Cassiopeia",
        "Cen": "Centaurus", "Cep": "Cepheus", "Cet": "Cetus",
        "Cha": "Chamaeleon", "Cir": "Circinus", "Col": "Columba",
        "Com": "Coma Berenices", "CrA": "Corona Australina", "CrB": "Corona Borealis",
        "Crv": "Corvus", "Crt": "Crater", "Cru": "Crux",
        "Cyg": "Cygnus", "Del": "Delphinus", "Dor": "Dorado",
        "Dra": "Draco", "Equ": "Equuleus", "Eri": "Eridanus",
        "For": "Fornax", "Gem": "Gemini", "Gru": "Grus",
        "Her": "Hercules", "Hor": "Horologium", "Hya": "Hydra",
        "Hyi": "Hydrus", "Ind": "Indus", "Lac": "Lacerta",
        "Leo": "Leo", "LMi": "Leo Minor", "Lep": "Lepus",
        "Lib": "Libra", "Lup": "Lupus", "Lyn": "Lynx",
        "Lyr": "Lyra", "Men": "Mensa", "Mic": "Microscopium",
        "Mon": "Monoceros", "Mus": "Musca", "Nor": "Norma",
        "Oct": "Octans", "Oph": "Ophiuchus", "Ori": "Orion",
        "Pav": "Pavo", "Peg": "Pegasus", "Per": "Perseus",
        "Phe": "Phoenix", "Pic": "Pictor", "Psc": "Pisces",
        "PsA": "Piscis Austrinus", "Pup": "Puppis", "Pyx": "Pyxis",
        "Ret": "Reticulum", "Sge": "Sagitta", "Sgr": "Sagittarius",
        "Sco": "Scorpius", "Scl": "Sculptor", "Sct": "Scutum",
        "Ser": "Serpens", "Sex": "Sextans", "Tau": "Taurus",
        "Tel": "Telescopium", "TrA": "Triangulum Australe", "Tri": "Triangulum",
        "Tuc": "Tucana", "UMa": "Ursa Major", "UMi": "Ursa Minor",
        "Vel": "Vela", "Vir": "Virgo", "Vol": "Volans",
        "Vul": "Vulpecula",
    },
}

SPECTRAL_COLORS: dict[str, str] = {
    "O": "#9bb0ff", "B": "#aabfff", "A": "#cad7ff",
    "F": "#f8f7ff", "G": "#fff4ea", "K": "#ffd2a1", "M": "#ffcc6f",
}

# ─── Japanese star names ─────────────────────────────────────────────────────────

STAR_NAMES_JA: dict[str, str] = {
    "Sirius": "シリウス", "Canopus": "カノープス",
    "Arcturus": "アークトゥルス", "Rigil Kentaurus": "リギル・ケンタウルス",
    "Vega": "ベガ", "Capella": "カペラ", "Rigel": "リゲル",
    "Procyon": "プロキオン", "Achernar": "アケルナル",
    "Betelgeuse": "ベテルギウス", "Hadar": "ハダル",
    "Altair": "アルタイル", "Acrux": "アクルックス",
    "Aldebaran": "アルデバラン", "Spica": "スピカ",
    "Antares": "アンタレス", "Pollux": "ポルックス",
    "Fomalhaut": "フォーマルハウト", "Deneb": "デネブ",
    "Mimosa": "ミモザ", "Regulus": "レグルス",
    "Adhara": "アダラ", "Shaula": "シャウラ",
    "Castor": "カストル", "Gacrux": "ガクルックス",
    "Bellatrix": "ベラトリックス", "Elnath": "エルナト",
    "Alioth": "アリオト", "Dubhe": "ドゥーベ",
    "Mirfak": "ミルファク", "Alkaid": "アルカイド",
    "Alnitak": "アルニタク", "Alnilam": "アルニラム",
    "Mintaka": "ミンタカ", "Alphard": "アルファルド",
    "Polaris": "ポラリス", "Mizar": "ミザール",
    "Merak": "メラク", "Phecda": "フェクダ",
    "Denebola": "デネボラ", "Rasalhague": "ラス・アルハゲ",
    "Kochab": "コカブ", "Alphecca": "アルフェッカ",
    "Saiph": "サイフ", "Alpheratz": "アルフェラッツ",
    "Markab": "マルカブ", "Scheat": "シェアト",
    "Algenib": "アルゲニブ", "Hamal": "ハマル",
    "Diphda": "ディフダ", "Nunki": "ヌンキ",
    "Enif": "エニフ", "Izar": "イザール",
    "Eltanin": "エルタニン", "Kaus Australis": "カウス・アウストラリス",
    "Peacock": "ピーコック", "Atria": "アトリア",
    "Alhena": "アルヘナ", "Miaplacidus": "ミアプラキドゥス",
    "Avior": "アビオール", "Sargas": "サルガス",
    "Wezen": "ウェゼン", "Mirzam": "ミルザム",
    "Naos": "ナオス", "Menkent": "メンケント",
    "Schedar": "シェダル", "Caph": "カフ", "Gienah": "ギエナ",
}

# ─── City presets ────────────────────────────────────────────────────────────────

CITIES: dict[str, tuple[float, float, str]] = {
    "東京": (35.6762, 139.6503, "Asia/Tokyo"),
    "Tokyo": (35.6762, 139.6503, "Asia/Tokyo"),
    "大阪": (34.6937, 135.5023, "Asia/Tokyo"),
    "Osaka": (34.6937, 135.5023, "Asia/Tokyo"),
    "名古屋": (35.1815, 136.9066, "Asia/Tokyo"),
    "Nagoya": (35.1815, 136.9066, "Asia/Tokyo"),
    "札幌": (43.0642, 141.3469, "Asia/Tokyo"),
    "Sapporo": (43.0642, 141.3469, "Asia/Tokyo"),
    "仙台": (38.2682, 140.8694, "Asia/Tokyo"),
    "Sendai": (38.2682, 140.8694, "Asia/Tokyo"),
    "横浜": (35.4437, 139.6380, "Asia/Tokyo"),
    "Yokohama": (35.4437, 139.6380, "Asia/Tokyo"),
    "京都": (35.0116, 135.7681, "Asia/Tokyo"),
    "Kyoto": (35.0116, 135.7681, "Asia/Tokyo"),
    "神戸": (34.6901, 135.1956, "Asia/Tokyo"),
    "Kobe": (34.6901, 135.1956, "Asia/Tokyo"),
    "広島": (34.3853, 132.4553, "Asia/Tokyo"),
    "Hiroshima": (34.3853, 132.4553, "Asia/Tokyo"),
    "福岡": (33.5904, 130.4017, "Asia/Tokyo"),
    "Fukuoka": (33.5904, 130.4017, "Asia/Tokyo"),
    "那覇": (26.2124, 127.6792, "Asia/Tokyo"),
    "Naha": (26.2124, 127.6792, "Asia/Tokyo"),
    "New York": (40.7128, -74.0060, "America/New_York"),
    "Los Angeles": (34.0522, -118.2437, "America/Los_Angeles"),
    "Chicago": (41.8781, -87.6298, "America/Chicago"),
    "Honolulu": (21.3069, -157.8583, "Pacific/Honolulu"),
    "London": (51.5074, -0.1278, "Europe/London"),
    "Paris": (48.8566, 2.3522, "Europe/Paris"),
    "Berlin": (52.5200, 13.4050, "Europe/Berlin"),
    "Sydney": (-33.8688, 151.2093, "Australia/Sydney"),
    "Beijing": (39.9042, 116.4074, "Asia/Shanghai"),
    "Seoul": (37.5665, 126.9780, "Asia/Seoul"),
    "Singapore": (1.3521, 103.8198, "Asia/Singapore"),
}

# ─── Seasonal asterisms ──────────────────────────────────────────────────────────

ASTERISMS: list[dict] = [
    {
        "ja": "春の大曲線", "en": "Spring Arc",
        "hip": [62956, 65378, 67301, 69673, 65474],
        "label_hip": 69673, "color": "#66cc88", "closed": False,
    },
    {
        "ja": "春の大三角", "en": "Spring Triangle",
        "hip": [69673, 65474, 57632],
        "label_hip": None, "color": "#55ccbb", "closed": True,
    },
    {
        "ja": "夏の大三角", "en": "Summer Triangle",
        "hip": [91262, 102098, 97649],
        "label_hip": 102098, "color": "#8899ff", "closed": True,
    },
    {
        "ja": "秋の大四辺形", "en": "Autumn Square",
        "hip": [113963, 113881, 677, 1067],
        "label_hip": None, "color": "#ffaa44", "closed": True,
    },
    {
        "ja": "冬の大三角", "en": "Winter Triangle",
        "hip": [32349, 27989, 37279],
        "label_hip": 27989, "color": "#ff8866", "closed": True,
    },
    {
        "ja": "冬の大六角形", "en": "Winter Hexagon",
        "hip": [32349, 24436, 21421, 24608, 37826, 37279],
        "label_hip": 24608, "color": "#ffdd88", "closed": True,
    },
]

# ─── Helpers ────────────────────────────────────────────────────────────────────

def setup_font(lang: str) -> None:
    candidates = (
        ["Yu Gothic", "Yu Gothic UI", "Meiryo", "MS Gothic",
         "Noto Sans CJK JP", "IPAexGothic", "TakaoPGothic"]
        if lang == "ja" else []
    )
    for name in candidates:
        try:
            fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
            plt.rcParams["font.family"] = name
            return
        except Exception:
            continue


def _download(url: str, label: str) -> bytes:
    print(f"  Downloading {label} …", flush=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def load_hyg_catalog(force: bool = False) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not force and HYG_CACHE.exists():
        with HYG_CACHE.open("rb") as f:
            return pickle.load(f)

    raw: bytes | None = None
    for url, is_gz in HYG_URLS:
        try:
            raw_bytes = _download(url, "HYG star catalog")
            raw = gzip.decompress(raw_bytes) if is_gz else raw_bytes
            break
        except Exception as e:
            print(f"  Warning: {url} failed ({e})")
    if raw is None:
        raise RuntimeError("Could not download HYG star catalog. Check your internet connection.")

    stars: list[dict] = []
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        try:
            mag = float(row["mag"])
            if mag > 6.5:
                continue
            stars.append({
                "hip":    int(row["hip"]) if row.get("hip", "").strip() else 0,
                "ra":     float(row["ra"]) * 15.0,
                "dec":    float(row["dec"]),
                "mag":    mag,
                "proper": row.get("proper", "").strip(),
                "spect":  row.get("spect", "").strip(),
            })
        except (ValueError, KeyError):
            continue

    with HYG_CACHE.open("wb") as f:
        pickle.dump(stars, f)
    print(f"  Cached {len(stars):,} stars (mag ≤ 6.5)")
    return stars


def load_constellation_lines(force: bool = False) -> dict[str, list[tuple[int, int]]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not force and CONST_CACHE.exists():
        with CONST_CACHE.open("rb") as f:
            return pickle.load(f)

    try:
        raw = _download(CONST_URL, "constellation lines")
    except Exception as e:
        print(f"  Warning: Could not download constellation data ({e}). Lines will be skipped.")
        return {}

    data = json.loads(raw.decode("utf-8"))

    constellations: dict[str, list[tuple[int, int]]] = {}
    for entry in data.get("constellations", []):
        con_id = entry.get("id", "")
        parts = con_id.split()
        abbrev = parts[-1] if parts else con_id
        segs: list[tuple[int, int]] = []
        for polyline in entry.get("lines", []):
            for i in range(len(polyline) - 1):
                segs.append((polyline[i], polyline[i + 1]))
        constellations.setdefault(abbrev, []).extend(segs)

    with CONST_CACHE.open("wb") as f:
        pickle.dump(constellations, f)
    print(f"  Cached {len(constellations)} constellations")
    return constellations


# ─── Coordinate transform ───────────────────────────────────────────────────────

def altaz_to_xy(alt: float, az: float, center_az: float | None = None) -> tuple[float, float]:
    """Altitude/azimuth → plot (x, y).

    center_az=None: azimuthal equidistant, North up, zenith at (0, 0).
    center_az=float: orthographic projection; horizon at y=0, zenith at (0, 90),
                     specified direction at bottom centre.
    """
    if center_az is not None:
        daz = math.radians(az - center_az)
        alt_r = math.radians(alt)
        return math.cos(alt_r) * math.sin(daz) * 90.0, math.sin(alt_r) * 90.0
    r = 90.0 - alt
    a = math.radians(az)
    return -r * math.sin(a), r * math.cos(a)


def in_view_half(az: float, center_az: float) -> bool:
    """True when az is within the ±90° semicircle centred on center_az."""
    d = ((az - center_az + 180.0) % 360.0) - 180.0
    return abs(d) <= 90.5


def star_color(spect: str) -> str:
    return SPECTRAL_COLORS.get(spect[:1].upper(), "#ffffff") if spect else "#ffffff"


def mag_to_size(mag: float) -> float:
    return max(0.5, (6.0 - mag) ** 2.0 * 0.8)


# ─── Drawing routines ───────────────────────────────────────────────────────────

def _horizon_clip_patch(ax) -> mpatches.Circle:
    return mpatches.Circle((0, 0), 90.0, transform=ax.transData)


def _semi_clip_patch(ax) -> PathPatch:
    θ = np.linspace(0, math.pi, 181)
    arc_x = 90 * np.cos(θ)
    arc_y = 90 * np.sin(θ)
    verts = list(zip(arc_x, arc_y))
    codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(arc_x) - 1)
    verts.append((arc_x[0], arc_y[0]))
    codes.append(MplPath.CLOSEPOLY)
    return PathPatch(MplPath(np.array(verts), codes), transform=ax.transData)


def draw_sky_background(ax, semi: bool = False) -> None:
    if semi:
        θ = np.linspace(0, math.pi, 181)
        verts = list(zip(90 * np.cos(θ), 90 * np.sin(θ)))
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * 180
        verts.append((90.0, 0.0))
        codes.append(MplPath.CLOSEPOLY)
        ax.add_patch(PathPatch(MplPath(np.array(verts), codes),
                               facecolor="#070715", edgecolor="none", zorder=0))
    else:
        ax.add_patch(mpatches.Circle((0, 0), 90, color="#070715", zorder=0))
        for r, alpha in [(85, 0.06), (70, 0.04), (50, 0.03)]:
            ax.add_patch(mpatches.Circle((0, 0), r, color="#0a1030", alpha=alpha,
                                         zorder=0, linewidth=0))


def draw_horizon_mask(ax, semi: bool = False) -> None:
    θ = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    ox, oy = 200 * np.cos(θ), 200 * np.sin(θ)
    ix, iy = 90 * np.cos(-θ),  90 * np.sin(-θ)
    verts = np.vstack([np.column_stack([ox, oy]), [ox[0], oy[0]],
                       np.column_stack([ix, iy]), [ix[0], iy[0]]])
    codes = ([MplPath.MOVETO] + [MplPath.LINETO] * (len(ox) - 1) + [MplPath.CLOSEPOLY]
             + [MplPath.MOVETO] + [MplPath.LINETO] * (len(ix) - 1) + [MplPath.CLOSEPOLY])
    ax.add_patch(PathPatch(MplPath(verts, codes),
                           facecolor="#070715", edgecolor="none", zorder=7))
    if semi:
        ax.add_patch(mpatches.Rectangle((-110, -110), 220, 110,
                                         facecolor="#070715", edgecolor="none", zorder=7))


def draw_grid(ax, lang: str, center_az: float | None = None) -> None:
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)

    if is_semi:
        for alt in (30, 60):
            y_alt = math.sin(math.radians(alt)) * 90
            x_alt = math.cos(math.radians(alt)) * 90
            ax.plot([-x_alt, x_alt], [y_alt, y_alt], color="#1e3050",
                    linewidth=0.6, linestyle="--", zorder=1)
            ax.text(x_alt + 1.5, y_alt, f"{alt}°", color="#3a5070", fontsize=7,
                    ha="left", va="center", zorder=8)

        for label_en, az, label_jp in DIRECTIONS_8:
            if not in_view_half(az, center_az):
                continue
            daz = math.radians(az - center_az)
            x_hor = math.sin(daz) * 90
            ax.plot([0, x_hor], [90, 0], color="#1a2a40",
                    linewidth=0.5, linestyle="--", zorder=1)
            lbl = label_jp if lang == "ja" else label_en
            ax.text(x_hor, -5, lbl, color="#6699cc", fontsize=11,
                    ha="center", va="top", fontweight="bold", zorder=9)

        ax.plot([-90, 90], [0, 0], color="#2a4a70", linewidth=2.0, zorder=8)
        θ = np.linspace(0, math.pi, 181)
        ax.plot(90 * np.cos(θ), 90 * np.sin(θ), color="#2a4a70", linewidth=2.0, zorder=8)
        ax.plot(0, 90, "+", color="#2a4a70", markersize=8, markeredgewidth=1, zorder=9)
        zen_lbl = "天頂" if lang == "ja" else "Zenith"
        ax.text(0, 91.5, zen_lbl, color="#3a5070", fontsize=7,
                ha="center", va="bottom", zorder=9)
    else:
        for alt in (30, 60):
            r = 90 - alt
            ax.add_patch(mpatches.Circle((0, 0), r, fill=False, edgecolor="#1e3050",
                                         linewidth=0.6, linestyle="--", zorder=1))
            ax.text(1.5, r + 1.5, f"{alt}°", color="#3a5070", fontsize=7,
                    ha="left", va="bottom", zorder=8)

        for label_en, az, label_jp in DIRECTIONS_8:
            x_hor, y_hor = altaz_to_xy(0, az)
            line, = ax.plot([0, x_hor], [0, y_hor], color="#1a2a40",
                            linewidth=0.5, linestyle="--", zorder=1)
            line.set_clip_path(clip)
            lbl = label_jp if lang == "ja" else label_en
            xl = -98 * math.sin(math.radians(az))
            yl = 98 * math.cos(math.radians(az))
            ax.text(xl, yl, lbl, color="#6699cc", fontsize=11,
                    ha="center", va="center", fontweight="bold", zorder=9)

        ax.add_patch(mpatches.Circle((0, 0), 90, fill=False, edgecolor="#2a4a70",
                                     linewidth=2.0, zorder=8))
        ax.plot(0, 0, "+", color="#2a4a70", markersize=8, markeredgewidth=1, zorder=9)


def draw_constellation_lines(
    ax,
    const_lines: dict[str, list[tuple[int, int]]],
    hip_altaz: dict[int, tuple[float, float]],
    show_names: bool,
    lang: str,
    center_az: float | None = None,
) -> None:
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)
    segments: list[tuple] = []

    for abbrev, segs in const_lines.items():
        pts: list[tuple[float, float]] = []
        for h1, h2 in segs:
            if h1 not in hip_altaz or h2 not in hip_altaz:
                continue
            alt1, az1 = hip_altaz[h1]
            alt2, az2 = hip_altaz[h2]
            if alt1 < -5 and alt2 < -5:
                continue
            if is_semi and not (in_view_half(az1, center_az) and in_view_half(az2, center_az)):
                continue
            x1, y1 = altaz_to_xy(max(alt1, -5.0), az1, center_az)
            x2, y2 = altaz_to_xy(max(alt2, -5.0), az2, center_az)
            segments.append(((x1, y1), (x2, y2)))
            pts += [(x1, y1), (x2, y2)]

        if show_names and pts:
            vis = [(x, y) for x, y in pts
                   if math.hypot(x, y) < 87 and (not is_semi or y >= 5)]
            if vis:
                cx = sum(x for x, _ in vis) / len(vis)
                cy = sum(y for _, y in vis) / len(vis)
                if not is_semi or cy >= 5:
                    name = CONSTELLATION_NAMES.get(lang, CONSTELLATION_NAMES["en"]).get(abbrev, abbrev)
                    ax.text(cx, cy, name, color="#4466aa", fontsize=7.5,
                            ha="center", va="center", alpha=0.85, zorder=3)

    if segments:
        lc = LineCollection(segments, color="#4a6fc0", linewidth=1.4,
                            alpha=0.90, zorder=2)
        lc.set_clip_path(clip)
        ax.add_collection(lc)


def draw_stars(
    ax,
    stars: list[dict],
    alts: np.ndarray,
    azs: np.ndarray,
    min_mag: float,
    show_names: bool,
    center_az: float | None = None,
    lang: str = "ja",
) -> None:
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)
    xs, ys, sizes, colors = [], [], [], []
    label_cands: list[tuple[float, float, float, str]] = []

    for i, star in enumerate(stars):
        mag = star["mag"]
        if mag > min_mag:
            continue
        alt = float(alts[i])
        az = float(azs[i])
        if alt < 0:
            continue
        if is_semi and not in_view_half(az, center_az):
            continue
        x, y = altaz_to_xy(alt, az, center_az)
        xs.append(x)
        ys.append(y)
        sizes.append(mag_to_size(mag))
        colors.append(star_color(star["spect"]))
        if show_names and star["proper"] and mag <= 1.0:
            sname = (STAR_NAMES_JA.get(star["proper"], star["proper"])
                     if lang == "ja" else star["proper"])
            label_cands.append((mag, x, y, sname))

    if xs:
        sc = ax.scatter(xs, ys, s=sizes, c=colors, zorder=4,
                        linewidths=0, alpha=0.95)
        sc.set_clip_path(clip)

    label_cands.sort()
    placed: list[tuple[float, float]] = []
    for mag, x, y, name in label_cands:
        if any(math.hypot(x - px, y - py) < 4.5 for px, py in placed):
            continue
        ax.text(x + 1.3, y + 1.3, name, color="#99bbcc", fontsize=7,
                ha="left", va="bottom", zorder=5, alpha=0.9)
        placed.append((x, y))


def draw_planets(
    ax,
    planet_data: dict[str, dict],
    show_names: bool,
    lang: str,
    center_az: float | None = None,
) -> None:
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)
    names = PLANET_NAMES.get(lang, PLANET_NAMES["en"])

    for body, data in planet_data.items():
        alt, az = data["alt"], data["az"]
        if alt < 0:
            continue
        if is_semi and not in_view_half(az, center_az):
            continue
        x, y = altaz_to_xy(alt, az, center_az)
        if math.hypot(x, y) > 90:
            continue
        color = PLANET_COLORS.get(body, "#ffffff")
        size = 220 if body == "moon" else 90
        marker = "o" if body == "moon" else "D"
        sc = ax.scatter([x], [y], s=size, c=color, marker=marker, zorder=6,
                        linewidths=1.2, edgecolors="white", alpha=0.95)
        sc.set_clip_path(clip)
        if show_names:
            name = names.get(body, body)
            ax.text(x + 2.2, y + 2.2, name, color=color, fontsize=8.5,
                    ha="left", va="bottom", fontweight="bold", zorder=7)


def draw_milky_way(ax, altaz_frame, center_az: float | None = None) -> None:
    """Render the Milky Way as a smoothed 2-D density map of galactic-plane samples."""
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)
    rng = np.random.default_rng(42)

    n = 14000
    l = rng.uniform(0, 360, n)
    dist_c = np.minimum(l, 360 - l)
    sigma_b = 5.0 + 7.5 * np.exp(-(dist_c ** 2) / (2 * 45 ** 2))
    b = rng.normal(0, sigma_b)
    l = np.concatenate([l, rng.normal(0, 12, 3000) % 360])
    b = np.concatenate([b, rng.normal(0, 4.0, 3000)])

    aa = SkyCoord(l=l * u.deg, b=b * u.deg, frame='galactic').transform_to(altaz_frame)
    alts, azs = aa.alt.deg, aa.az.deg

    mask = alts > 0
    if is_semi:
        mask &= np.array([in_view_half(float(az), center_az) for az in azs])
    if not mask.any():
        return
    alts, azs = alts[mask], azs[mask]

    xy = np.array([altaz_to_xy(float(a), float(az), center_az)
                   for a, az in zip(alts, azs)])
    xs, ys = xy[:, 0], xy[:, 1]

    res = 160
    xr = (-92.0, 92.0)
    yr = (0.0, 92.0) if is_semi else (-92.0, 92.0)
    H, xe, ye = np.histogram2d(xs, ys, bins=res, range=[xr, yr])

    sigma = 4
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2)
    k /= k.sum()
    H = np.apply_along_axis(lambda a: np.convolve(a, k, mode='same'), 0, H.astype(float))
    H = np.apply_along_axis(lambda a: np.convolve(a, k, mode='same'), 1, H)

    nonzero = H[H > 0]
    vmax = float(np.percentile(nonzero, 95)) if nonzero.size else 1.0
    H = np.clip(H / vmax, 0.0, 1.0)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        'mw',
        [(0.00, (0.04, 0.06, 0.10, 0.00)),
         (0.15, (0.25, 0.38, 0.58, 0.06)),
         (0.50, (0.50, 0.64, 0.82, 0.13)),
         (1.00, (0.78, 0.88, 1.00, 0.22))],
        N=256,
    )
    extent = [xe[0], xe[-1], ye[0], ye[-1]]
    im = ax.imshow(H.T, extent=extent, origin='lower', cmap=cmap,
                   vmin=0, vmax=1, aspect='auto', zorder=1,
                   interpolation='bilinear')
    im.set_clip_path(clip)


def draw_asterisms(
    ax,
    hip_altaz: dict[int, tuple[float, float]],
    show_names: bool,
    lang: str,
    center_az: float | None = None,
) -> None:
    is_semi = center_az is not None
    clip = _semi_clip_patch(ax) if is_semi else _horizon_clip_patch(ax)

    def _xy(h: int) -> tuple[float, float] | None:
        if h not in hip_altaz:
            return None
        alt, az = hip_altaz[h]
        if is_semi and not in_view_half(az, center_az):
            return None
        return altaz_to_xy(alt, az, center_az)

    for ast in ASTERISMS:
        color = ast["color"]
        name = ast["ja"] if lang == "ja" else ast["en"]
        xys: list[tuple[float, float] | None] = [_xy(h) for h in ast["hip"]]
        if ast["closed"] and xys and xys[0] is not None:
            xys.append(xys[0])

        segments: list[tuple] = [
            (xys[i], xys[i + 1])
            for i in range(len(xys) - 1)
            if xys[i] is not None and xys[i + 1] is not None
        ]
        if not segments:
            continue

        lc = LineCollection(segments, color=color, linewidth=1.8,
                            alpha=0.65, linestyle="--", zorder=2)
        lc.set_clip_path(clip)
        ax.add_collection(lc)

        if show_names:
            def _in_bounds(pt: tuple[float, float]) -> bool:
                x, y = pt
                return math.hypot(x, y) <= 87 and (not is_semi or y >= 1)

            lhip = ast.get("label_hip")
            label_pos: tuple[float, float] | None = None
            if lhip:
                raw = _xy(lhip)
                if raw is not None and _in_bounds(raw):
                    label_pos = raw
            if label_pos is None:
                vis = [p for p in xys if p is not None and _in_bounds(p)]
                if vis:
                    label_pos = (
                        sum(x for x, _ in vis) / len(vis),
                        sum(y for _, y in vis) / len(vis),
                    )
            if label_pos is not None:
                ax.text(label_pos[0], label_pos[1], name,
                        color=color, fontsize=8, ha="center", va="center",
                        alpha=0.92, zorder=4, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="#070715",
                                  edgecolor="none", alpha=0.65))


# ─── Chart generation ───────────────────────────────────────────────────────────

def generate_chart(args) -> None:
    """Generate a star chart image.

    args must expose the same attributes as the CLI namespace:
    city, lat, lon, elevation, location_name, datetime, timezone, lang,
    direction, min_mag, no_milky_way, no_constellation_lines,
    no_constellation_names, no_star_names, no_planet_names, no_asterisms,
    title, dpi, force_refresh, output.
    """
    setup_font(args.lang)

    if args.city:
        if args.city not in CITIES:
            raise ValueError(f"Unknown city '{args.city}'. Valid: {', '.join(CITIES)}")
        args.lat, args.lon, args.timezone = CITIES[args.city]
        if not args.location_name:
            args.location_name = args.city

    tz = ZoneInfo(args.timezone)
    if args.datetime:
        local_dt = datetime.fromisoformat(args.datetime).replace(tzinfo=tz)
    else:
        local_dt = datetime.now(tz=tz)
    obs_time = Time(local_dt.astimezone(ZoneInfo("UTC")))

    location = EarthLocation(
        lat=args.lat * u.deg,
        lon=args.lon * u.deg,
        height=args.elevation * u.m,
    )
    altaz_frame = AltAz(obstime=obs_time, location=location)

    print("Loading star catalog …")
    stars = load_hyg_catalog(args.force_refresh)
    print("Loading constellation data …")
    const_lines = load_constellation_lines(args.force_refresh)

    print("Computing star positions …")
    star_coords = SkyCoord(
        ra=np.array([s["ra"] for s in stars]) * u.deg,
        dec=np.array([s["dec"] for s in stars]) * u.deg,
        frame="icrs",
    )
    result = star_coords.transform_to(altaz_frame)
    star_alts: np.ndarray = result.alt.deg
    star_azs: np.ndarray = result.az.deg

    hip_altaz: dict[int, tuple[float, float]] = {
        s["hip"]: (float(star_alts[i]), float(star_azs[i]))
        for i, s in enumerate(stars) if s["hip"]
    }

    print("Computing planet positions …")
    planet_data: dict[str, dict] = {}
    with solar_system_ephemeris.set("builtin"):
        for body in PLANETS:
            try:
                coord = get_body(body, obs_time, location)
                aa = coord.transform_to(altaz_frame)
                planet_data[body] = {"alt": float(aa.alt.deg), "az": float(aa.az.deg)}
            except Exception as e:
                print(f"  Skipping {body}: {e}")

    center_az: float | None = None
    if args.direction:
        center_az = DIRECTION_TO_AZ.get(args.direction)
        if center_az is None:
            raise ValueError(
                f"Unknown direction '{args.direction}'. "
                f"Valid: {', '.join(DIRECTION_TO_AZ)}"
            )

    is_semi = center_az is not None

    print("Rendering chart …")
    if is_semi:
        fig, ax = plt.subplots(figsize=(14, 8), facecolor="#070715")
    else:
        fig, ax = plt.subplots(figsize=(14, 14), facecolor="#070715")
    ax.set_facecolor("#070715")
    ax.set_aspect("equal")
    if is_semi:
        ax.set_xlim(-100, 100)
        ax.set_ylim(-15, 100)
    else:
        ax.set_xlim(-108, 108)
        ax.set_ylim(-108, 108)
    ax.axis("off")

    draw_sky_background(ax, semi=is_semi)

    if not args.no_milky_way:
        draw_milky_way(ax, altaz_frame, center_az=center_az)

    if not args.no_constellation_lines or not args.no_constellation_names:
        draw_constellation_lines(
            ax, const_lines, hip_altaz,
            show_names=not args.no_constellation_names,
            lang=args.lang,
            center_az=center_az,
        )

    if not args.no_asterisms:
        draw_asterisms(ax, hip_altaz,
                       show_names=True,
                       lang=args.lang,
                       center_az=center_az)

    draw_stars(ax, stars, star_alts, star_azs,
               args.min_mag, show_names=not args.no_star_names,
               center_az=center_az, lang=args.lang)

    draw_planets(ax, planet_data,
                 show_names=not args.no_planet_names, lang=args.lang,
                 center_az=center_az)

    draw_horizon_mask(ax, semi=is_semi)
    draw_grid(ax, args.lang, center_az=center_az)

    loc_name = args.location_name or f"{args.lat:+.4f}°, {args.lon:+.4f}°"
    time_str = local_dt.strftime("%Y-%m-%d  %H:%M  %Z")
    if args.title:
        main_title = args.title
    else:
        base = "星図" if args.lang == "ja" else "Star Chart"
        if is_semi:
            main_title = f"{base}  —  {loc_name}  [{args.direction}方向]"
        else:
            main_title = f"{base}  —  {loc_name}"

    if is_semi:
        ax.text(97, 94, main_title, color="#7799cc", fontsize=11,
                ha="right", va="top", zorder=10)
        ax.text(97, 87, time_str, color="#556688", fontsize=9,
                ha="right", va="top", zorder=10)
    else:
        ax.text(0, 106, main_title, color="#7799cc", fontsize=12,
                ha="center", va="bottom", zorder=10)
        ax.text(0, 102, time_str, color="#556688", fontsize=9,
                ha="center", va="bottom", zorder=10)

    visible_planets = [b for b, d in planet_data.items() if d["alt"] >= 0]
    if visible_planets:
        names_map = PLANET_NAMES.get(args.lang, PLANET_NAMES["en"])
        legend_text = ("可視惑星: " if args.lang == "ja" else "Visible: ") + \
                      "  ".join(names_map[b] for b in visible_planets)
        legend_y = -12 if is_semi else -104
        ax.text(0, legend_y, legend_text, color="#556688", fontsize=8,
                ha="center", va="top", zorder=10)

    fig.savefig(args.output, dpi=args.dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {args.output}")
