#!/usr/bin/env python3
"""Generate a Pioneer partial star catalog from HYG v42.

The old script expected two intermediate CSV files. HYG v42 already contains
the fields needed for Pioneer, so this generator uses only hyg_v42.csv.

It intentionally keeps the full catalog, including Sol. To avoid duplicates
inside the generated catalog, it:

- groups multi-star components by comp_primary,
- merges systems that resolve to the exact same Pioneer sector / position,
- assigns globally-unique primary names,
- avoids reusing aliases across different generated systems.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATHS = (
    SCRIPT_DIR / "hyg_v42.csv",
    SCRIPT_DIR / "data" / "hyg_v42.csv",
)
OUT_PATH = SCRIPT_DIR / "hyg_stars.json"
REPORT_PATH = SCRIPT_DIR / "hyg_stars_report.json"
LEGACY_COPY_PATH = SCRIPT_DIR / "hyg_stars_legacy_before_regen.json"

LY_PER_PARSEC = 3.26156
SECTOR_SIZE_LY = 8.0
SECTOR_SCALE = LY_PER_PARSEC / SECTOR_SIZE_LY
MAX_PIONEER_STARS = 4

PREFERRED_PRIMARY_NAMES = {
    # HYG stores Alpha Centauri A under the proper name Rigil Kentaurus and
    # Alpha Centauri B under Toliman. Pioneer displays one generated system for
    # the close A/B pair, so use the familiar system name as the primary label.
    "Rigil Kentaurus": "Alpha Centauri",
}

CONSTELLATIONS = {
    "And": "Andromedae",
    "Ant": "Antliae",
    "Aps": "Apodis",
    "Aqr": "Aquarii",
    "Aql": "Aquilae",
    "Ara": "Arae",
    "Ari": "Arietis",
    "Aur": "Aurigae",
    "Boo": "Boötis",
    "Cae": "Caeli",
    "Cam": "Camelopardalis",
    "Cnc": "Cancri",
    "CVn": "Canum Venaticorum",
    "CMa": "Canis Majoris",
    "CMi": "Canis Minoris",
    "Cap": "Capricorni",
    "Car": "Carinae",
    "Cas": "Cassiopeiae",
    "Cen": "Centauri",
    "Cep": "Cephei",
    "Cet": "Ceti",
    "Cha": "Chamaeleontis",
    "Cir": "Circini",
    "Col": "Columbae",
    "Com": "Comae Berenices",
    "CrA": "Coronae Australis",
    "CrB": "Coronae Borealis",
    "Crv": "Corvi",
    "Crt": "Crateris",
    "Cru": "Crucis",
    "Cyg": "Cygni",
    "Del": "Delphini",
    "Dor": "Doradus",
    "Dra": "Draconis",
    "Equ": "Equulei",
    "Eri": "Eridani",
    "For": "Fornacis",
    "Gem": "Geminorum",
    "Gru": "Gruis",
    "Her": "Herculis",
    "Hor": "Horologii",
    "Hya": "Hydrae",
    "Hyi": "Hydri",
    "Ind": "Indi",
    "Lac": "Lacertae",
    "Leo": "Leonis",
    "LMi": "Leonis Minoris",
    "Lep": "Leporis",
    "Lib": "Librae",
    "Lup": "Lupi",
    "Lyn": "Lyncis",
    "Lyr": "Lyrae",
    "Men": "Mensae",
    "Mic": "Microscopii",
    "Mon": "Monocerotis",
    "Mus": "Muscae",
    "Nor": "Normae",
    "Oct": "Octantis",
    "Oph": "Ophiuchi",
    "Ori": "Orionis",
    "Pav": "Pavonis",
    "Peg": "Pegasi",
    "Per": "Persei",
    "Phe": "Phoenicis",
    "Pic": "Pictoris",
    "Psc": "Piscium",
    "PsA": "Piscis Austrini",
    "Pup": "Puppis",
    "Pyx": "Pyxidis",
    "Ret": "Reticuli",
    "Sge": "Sagittae",
    "Sgr": "Sagittarii",
    "Sco": "Scorpii",
    "Scl": "Sculptoris",
    "Sct": "Scuti",
    "Ser": "Serpentis",
    "Sex": "Sextantis",
    "Tau": "Tauri",
    "Tel": "Telescopii",
    "Tri": "Trianguli",
    "TrA": "Trianguli Australis",
    "Tuc": "Tucanae",
    "UMa": "Ursae Majoris",
    "UMi": "Ursae Minoris",
    "Vel": "Velorum",
    "Vir": "Virginis",
    "Vol": "Volantis",
    "Vul": "Vulpeculae",
}

GREEK = {
    "Alp": "Alpha",
    "Bet": "Beta",
    "Gam": "Gamma",
    "Del": "Delta",
    "Eps": "Epsilon",
    "Zet": "Zeta",
    "Eta": "Eta",
    "The": "Theta",
    "Iot": "Iota",
    "Kap": "Kappa",
    "Lam": "Lambda",
    "Mu": "Mu",
    "Nu": "Nu",
    "Xi": "Xi",
    "Omi": "Omicron",
    "Pi": "Pi",
    "Rho": "Rho",
    "Sig": "Sigma",
    "Tau": "Tau",
    "Ups": "Upsilon",
    "Phi": "Phi",
    "Chi": "Chi",
    "Psi": "Psi",
    "Ome": "Omega",
}

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
VALID_TYPES = {
    "BROWN_DWARF",
    "WHITE_DWARF",
    "STAR_M",
    "STAR_K",
    "STAR_G",
    "STAR_F",
    "STAR_A",
    "STAR_B",
    "STAR_O",
    "STAR_M_GIANT",
    "STAR_K_GIANT",
    "STAR_G_GIANT",
    "STAR_F_GIANT",
    "STAR_A_GIANT",
    "STAR_B_GIANT",
    "STAR_O_GIANT",
    "STAR_M_SUPER_GIANT",
    "STAR_K_SUPER_GIANT",
    "STAR_G_SUPER_GIANT",
    "STAR_F_SUPER_GIANT",
    "STAR_A_SUPER_GIANT",
    "STAR_B_SUPER_GIANT",
    "STAR_O_SUPER_GIANT",
    "STAR_M_HYPER_GIANT",
    "STAR_K_HYPER_GIANT",
    "STAR_G_HYPER_GIANT",
    "STAR_F_HYPER_GIANT",
    "STAR_A_HYPER_GIANT",
    "STAR_B_HYPER_GIANT",
    "STAR_O_HYPER_GIANT",
    "STAR_M_WF",
    "STAR_B_WF",
    "STAR_O_WF",
    "STAR_S_BH",
    "STAR_IM_BH",
    "STAR_SM_BH",
}


def clean(text: str) -> str:
    return " ".join((text or "").replace('"', "").split())


def constellation(code: str) -> str:
    return CONSTELLATIONS.get(clean(code), clean(code))


def normalize_gliese(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    parts = value.split()
    if len(parts) < 2:
        return value
    prefix = parts[0]
    number = " ".join(parts[1:])
    if prefix == "Gl":
        return f"Gliese {number}"
    if prefix == "GJ":
        return f"GJ {number}"
    return value


def bayer_name(row: dict[str, str]) -> str:
    raw = clean(row["bayer"])
    con = constellation(row["con"])
    if not raw or not con:
        return ""
    parts = raw.split("-", 1)
    greek = GREEK.get(parts[0], parts[0])
    if len(parts) == 2:
        greek += parts[1].translate(SUPERSCRIPT)
    return f"{greek} {con}"


def flamsteed_name(row: dict[str, str]) -> str:
    flam = clean(row["flam"])
    con = constellation(row["con"])
    return f"{flam} {con}" if flam and con else ""


def variable_name(row: dict[str, str]) -> str:
    var = clean(row["var"])
    con = constellation(row["con"])
    return f"{var} {con}" if var and con else ""


def row_names(row: dict[str, str]) -> list[str]:
    names = [
        clean(row["proper"]),
        variable_name(row),
        bayer_name(row),
        flamsteed_name(row),
        normalize_gliese(row["gl"]),
        normalize_gliese(row["base"]),
        f"HR {clean(row['hr'])}" if clean(row["hr"]) else "",
        f"HD {clean(row['hd'])}" if clean(row["hd"]) else "",
        f"HIP {clean(row['hip'])}" if clean(row["hip"]) else "",
        f"HYG {clean(row['id'])}",
    ]
    return dedupe([name for name in names if name])


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def pioneer_type(row: dict[str, str]) -> str:
    raw = clean(row["spect"]).upper()
    lum = float(row["lum"] or 0)

    if raw.startswith("D"):
        return "WHITE_DWARF"

    spect = "M"
    for char in raw:
        if char in "WOBAFGKMLTYCRNS":
            spect = char
            break

    if spect == "W":
        return "STAR_O_WF"
    if spect in "LTY":
        return "BROWN_DWARF"
    if spect in "CRNS":
        return "STAR_M_GIANT" if lum > 1 else "STAR_M"

    if (spect in "OBAFG" and lum < 0.02) or (spect == "K" and lum < 0.0005):
        return "WHITE_DWARF"

    if lum > 100000:
        return f"STAR_{spect}_HYPER_GIANT"
    if lum > 30000:
        return f"STAR_{spect}_SUPER_GIANT"

    giant_thresholds = {"M": 8, "K": 8, "G": 8, "F": 20, "A": 40, "B": 100, "O": 1}
    if lum > giant_thresholds.get(spect, 8):
        return f"STAR_{spect}_GIANT"
    return f"STAR_{spect}"


def pioneer_position(row: dict[str, str]) -> tuple[list[int], list[float]]:
    # Pioneer uses a different galactic coordinate basis than HYG.
    x = float(row["y"]) * SECTOR_SCALE
    y = -float(row["x"]) * SECTOR_SCALE
    z = float(row["z"]) * SECTOR_SCALE
    sector = [math.floor(x), math.floor(y), math.floor(z)]
    pos = [round((x - sector[0]) * SECTOR_SIZE_LY, 6), round((y - sector[1]) * SECTOR_SIZE_LY, 6), round((z - sector[2]) * SECTOR_SIZE_LY, 6)]
    # Keep values safely inside the sector after decimal rounding.
    for idx, value in enumerate(pos):
        if value >= SECTOR_SIZE_LY:
            sector[idx] += 1
            pos[idx] = 0.0
    return sector, pos


def load_rows() -> list[dict[str, str]]:
    csv_path = next((path for path in CSV_PATHS if path.exists()), None)
    if csv_path is None:
        expected = ", ".join(str(path) for path in CSV_PATHS)
        raise FileNotFoundError(f"Could not find HYG CSV. Expected one of: {expected}")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def prefer_primary_name(names: list[str]) -> list[str]:
    for source_name, preferred_name in PREFERRED_PRIMARY_NAMES.items():
        if source_name in names:
            ordered = [preferred_name]
            ordered.extend(name for name in names if name != preferred_name)
            return dedupe(ordered)
    return names


def build_catalog(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {row["id"]: row for row in rows}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        primary_id = row["comp_primary"] or row["id"]
        if primary_id not in by_id:
            primary_id = row["id"]
        groups[primary_id].append(row)

    systems = []
    for primary_id, members in groups.items():
        primary = by_id.get(primary_id, members[0])
        sector, pos = pioneer_position(primary)
        names = []
        stars = []
        source_ids = []
        for member in sorted(members, key=lambda r: int(r["comp"] or 1)):
            source_ids.append(member["id"])
            names.extend(row_names(member))
            typ = pioneer_type(member)
            stars.append(typ if typ in VALID_TYPES else "STAR_M")
        systems.append({
            "sourceIds": source_ids,
            "names": prefer_primary_name(dedupe(names)),
            "stars": stars,
            "sector": sector,
            "pos": pos,
        })

    by_position: dict[tuple[tuple[int, int, int], tuple[float, float, float]], list[dict[str, Any]]] = defaultdict(list)
    for system in systems:
        by_position[(tuple(system["sector"]), tuple(system["pos"]))].append(system)

    merged = []
    merged_position_groups = 0
    truncated_star_components = 0
    for same_position in by_position.values():
        if len(same_position) > 1:
            merged_position_groups += 1
        names = []
        stars = []
        source_ids = []
        for system in same_position:
            names.extend(system["names"])
            stars.extend(system["stars"])
            source_ids.extend(system["sourceIds"])
        if len(stars) > MAX_PIONEER_STARS:
            truncated_star_components += len(stars) - MAX_PIONEER_STARS
            stars = stars[:MAX_PIONEER_STARS]
        merged.append({
            "sourceIds": source_ids,
            "names": prefer_primary_name(dedupe(names)),
            "stars": stars,
            "sector": same_position[0]["sector"],
            "pos": same_position[0]["pos"],
        })

    used_names = set()
    output = []
    renamed_duplicate_primaries = 0
    dropped_duplicate_aliases = 0
    for system in sorted(merged, key=lambda s: min(int(i) for i in s["sourceIds"])):
        primary = None
        for name in system["names"]:
            if name not in used_names:
                primary = name
                break
        if primary is None:
            primary = f"HYG {min(int(i) for i in system['sourceIds'])}"
        if primary != system["names"][0]:
            renamed_duplicate_primaries += 1
        used_names.add(primary)

        other_names = []
        for name in system["names"]:
            if name == primary:
                continue
            if name in used_names:
                dropped_duplicate_aliases += 1
                continue
            used_names.add(name)
            other_names.append(name)

        entry: dict[str, Any] = {
            "name": primary,
            "stars": system["stars"],
        }
        if other_names:
            entry["otherNames"] = other_names
        entry["sector"] = system["sector"]
        entry["pos"] = system["pos"]
        output.append(entry)

    report = {
        "source_rows": len(rows),
        "component_groups": len(groups),
        "generated_systems": len(output),
        "merged_exact_position_groups": merged_position_groups,
        "renamed_duplicate_primaries": renamed_duplicate_primaries,
        "dropped_duplicate_aliases": dropped_duplicate_aliases,
        "truncated_star_components": truncated_star_components,
        "primary_name_duplicates": count_duplicate_primary_names(output),
        "exact_position_duplicates": count_exact_position_duplicates(output),
        "contains_sol": any(system["name"] == "Sol" for system in output),
        "max_stars_per_system": max(len(system["stars"]) for system in output),
    }
    return output, report


def count_duplicate_primary_names(catalog: list[dict[str, Any]]) -> int:
    return sum(1 for count in Counter(system["name"] for system in catalog).values() if count > 1)


def count_exact_position_duplicates(catalog: list[dict[str, Any]]) -> int:
    positions = Counter((tuple(system["sector"]), tuple(system["pos"])) for system in catalog)
    return sum(1 for count in positions.values() if count > 1)


def summarize_catalog(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "systems": len(catalog),
        "primary_name_duplicates": count_duplicate_primary_names(catalog),
        "exact_position_duplicates": count_exact_position_duplicates(catalog),
        "contains_sol": any(system["name"] == "Sol" for system in catalog),
        "max_stars_per_system": max(len(system["stars"]) for system in catalog),
        "star_count_distribution": dict(sorted(Counter(len(system["stars"]) for system in catalog).items())),
    }


def write_catalog(catalog: list[dict[str, Any]]) -> None:
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write("[\n")
        for idx, system in enumerate(catalog):
            comma = "," if idx < len(catalog) - 1 else ""
            f.write("    " + json.dumps(system, ensure_ascii=False, separators=(", ", ": ")) + comma + "\n")
        f.write("]\n")


def main() -> None:
    legacy_summary = None
    legacy_path = LEGACY_COPY_PATH if LEGACY_COPY_PATH.exists() else OUT_PATH
    if legacy_path.exists():
        legacy_catalog = json.loads(legacy_path.read_text(encoding="utf-8"))
        legacy_summary = summarize_catalog(legacy_catalog)
        if OUT_PATH.exists() and not LEGACY_COPY_PATH.exists():
            shutil.copy2(OUT_PATH, LEGACY_COPY_PATH)

    rows = load_rows()
    catalog, report = build_catalog(rows)
    report["legacy_summary"] = legacy_summary
    report["new_summary"] = summarize_catalog(catalog)

    write_catalog(catalog)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
