# Pioneer HYG Stellar Catalog

This project converts the HYG stellar database into a Pioneer `systems/partial`
JSON catalog.

The generated catalog adds real-world star positions and names to Pioneer's
galaxy map. These are partial system definitions: Pioneer uses the listed star
name, type, sector, and position, then generates the rest of each system
procedurally when visited.

## Source Data

The source CSV is the HYG database from AstroNexus:

https://www.astronexus.com/projects/hyg

Download the HYG CSV manually and place it either next to `starz.py` or in the
local `data` directory as:

```text
hyg_v42.csv
data/hyg_v42.csv
```

Do not commit the downloaded CSV to the repository. It is source data from an
external project and should remain a local build input.

## Files

- `starz.py`: generator script that converts `hyg_v42.csv` to Pioneer JSON.
- `hyg_stars.json`: generated Pioneer partial-system catalog.
- `hyg_stars_report.json`: generated audit report comparing the regenerated
  catalog against the previous output when available.
- `hyg_stars_legacy_before_regen.json`: local backup of the old generated
  catalog, created once by the generator for comparison.
- `hyg_v42.csv` or `data/hyg_v42.csv`: local source CSV downloaded from
  AstroNexus. Do not commit.

## Installation

Copy the generated JSON into Pioneer's partial systems directory, for example:

```text
D:/Pioneer/data/systems/partial/02_hyg_stars.json
```

Pioneer loads every `.json` file in:

```text
data/systems/partial
```

If you want the HYG catalog to replace the vanilla partial catalogs, disable or
move the vanilla files first:

```text
02_local_stars.json
03_bright_stars.json
```

For example:

```text
02_local_stars.json.disabled
03_bright_stars.json.disabled
```

If you leave the vanilla partial catalogs enabled, Pioneer can load both sets.
That may be useful for testing, but it can also create duplicate or competing
real-star entries.

For example, Alpha Centauri exists in the generated HYG catalog. The generator
uses `Alpha Centauri` as the primary display name for the close A/B pair and
keeps `Rigil Kentaurus`, `Toliman`, `Alpha¹ Centauri`, and `Alpha² Centauri` as
aliases. If a separate vanilla Alpha Centauri also appears nearby, the vanilla
partial catalog is still enabled.

## Building

From this directory:

```text
python starz.py
```

The script reads:

```text
hyg_v42.csv
data/hyg_v42.csv
```

and writes:

```text
hyg_stars.json
hyg_stars_report.json
```

The old script expected both `hyg_v42.csv` and `hyg_v42-2.csv`. With the current
HYG v42 file, the second CSV is not needed; all required fields are already in
`hyg_v42.csv`.

## What The Generator Does

- Reads HYG v42 with Python's `csv.DictReader`.
- Converts HYG XYZ coordinates into Pioneer's sector / position format.
- Converts HYG spectral classes into Pioneer's supported star body types.
- Groups multi-star components by `comp_primary`.
- Preserves all source rows via `HYG <id>` aliases.
- Merges entries that resolve to the exact same Pioneer position.
- Ensures primary names are unique within the generated JSON.
- Avoids duplicate aliases across generated systems.
- Uses `Alpha Centauri` as the primary label for the HYG Alpha Centauri A/B
  group while preserving Rigil Kentaurus and Toliman as aliases.
- Writes valid UTF-8 JSON with `json.dumps`.

## Current Audit

At the time of the latest regeneration:

| Metric | Old output | New output |
| --- | ---: | ---: |
| Source CSV rows represented | 119,626 | 119,626 |
| Generated systems | 119,190 | 119,180 |
| Primary-name duplicates | 72 | 0 |
| Exact position duplicates | 10 | 0 |
| Missing HYG IDs | 0 | 0 |
| Max star components per system | 3 | 3 |
| Includes Sol | Yes | Yes |

The generated system count is lower than the CSV row count because Pioneer
partial systems represent star systems, not individual catalog rows. Multi-star
components are grouped into one Pioneer system, and exact position duplicates
are merged.

## Known Limitations

This is a real-star catalog, not a full astronomical simulation.

- It does not define real planets, moons, stations, or economies.
- Pioneer procedurally generates the rest of each system when visited.
- Multi-star systems are simplified to a list of star body types.
- Real binary separations, orbits, masses, and component hierarchy are not
  represented.
- HYG contains distant and uncertain catalog entries; the full catalog is large.
- Spectral classes that Pioneer does not support directly are approximated.
- Carbon stars, S stars, subdwarfs, and other unusual types are mapped to the
  nearest practical Pioneer star type.

## Testing In Pioneer

Pioneer may not print a success message when loading a partial catalog. A quiet
console usually means the JSON loaded without errors.

To test manually:

1. Install `hyg_stars.json` as `02_hyg_stars.json` in `data/systems/partial`.
2. Start Pioneer.
3. Search the galaxy map for less-common catalog entries such as:

```text
GJ 1111
HIP 82724
GJ 3522
Gliese 83.1
GJ 3618
```

If those stars appear and can be selected, the catalog is loading.

## License And Credits

Pioneer is licensed under the GNU General Public License version 3.

The original Pioneer stellar catalog mod was created by Hypernoot from the
unofficial Pioneer Discord:

https://discord.com/invite/RQQe3A7

The HYG database is provided by AstroNexus. Download it from:

https://www.astronexus.com/projects/hyg

Credit should be given to AstroNexus / the HYG database for the source catalog
data when distributing generated outputs or tools based on it.
