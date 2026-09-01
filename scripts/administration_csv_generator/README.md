# Administration CSV generator

Turns a GeoJSON of administrative boundaries into the CSV that
`administration_csv_seeder` imports, so a workspace can be given a real
hierarchy in one command.

```
GeoJSON  ->  this notebook  ->  storage/administrations/*.csv  ->  seeder  ->  workspace
```

Only `properties` is read from the GeoJSON. Geometry is ignored entirely —
the platform stores administrative units as a name/code tree, not as shapes.

---

## Quick start

```bash
cp config.json.example config.json
# put your file in geojson/ and edit config.json to match, then:
jupyter notebook administration_csv_generator.ipynb
```

Run the cells in order. Step 1 prints the properties of one feature so you
can fill in the mapping without guessing, and Step 1's last cell prints a
ready-to-paste `labels` + `properties` block guessed from the file.

Then import what it wrote:

```bash
# validates the whole file and rolls back
./dc.sh exec backend python manage.py administration_csv_seeder \
    --source administrations/indonesia.csv --tenant qa1 --dry-run

./dc.sh exec backend python manage.py administration_csv_seeder \
    --source administrations/indonesia.csv --tenant qa1
```

`config.json` and `geojson/*.geojson` are gitignored — country files are
operator data, not repository content. Only `config.json.example` is
committed.

---

## `config.json`

```json
{
  "input": "scripts/administration_csv_generator/geojson/Indonesia_Level_3.geojson",
  "output": "storage/administrations/indonesia.csv",
  "labels": {
    "0": "National",
    "1": "Province",
    "2": "Regency",
    "3": "Sub-district"
  },
  "properties": {
    "0_name": "COUNTRY",
    "0_code": "GID_0",
    "1_name": "NAME_1",
    "1_code": "GID_1",
    "2_name": "NAME_2",
    "2_code": "GID_2",
    "3_name": "NAME_3",
    "3_code": "GID_3"
  },
  "options": {
    "na_values": ["NA", "N/A", "NULL", ""],
    "split_camel_case": false
  }
}
```

| Field | Meaning |
|---|---|
| `input` | GeoJSON to read. **Relative to the repo root.** |
| `output` | CSV to write. Relative to the repo root, and must be under `storage/` (see below). |
| `labels` | `"<level>"` → what that tier is *called*. See the next section — this is not just a column heading. |
| `properties` | `"<level>_name"` / `"<level>_code"` → the GeoJSON property supplying it. `_code` is optional; omit the key to drop the column. |
| `options.na_values` | Values treated as empty. GADM writes the literal string `"NA"`, not null. |
| `options.split_camel_case` | Insert spaces into run-together names. Off by default — see Gotchas. |

Levels must run contiguously from 0. `0_name` is required; the seeder
refuses a file whose level-0 column is blank or holds more than one value,
because a workspace has exactly one root.

Both paths resolve from the repo root, which the notebook locates by walking
up to the directory containing `dc.sh`. That way the same `output` value
works whether you launch Jupyter from this directory or from the repo root.

---

## Why `labels` exists

The seeder's header format is `{level}_{Label}` for names and
`{level}_Code` for codes:

```
0_National,0_Code,1_Province,1_Code,2_Regency,2_Code,3_Sub-district,3_Code
Indonesia,IDN,Aceh,IDN.1_1,AcehBarat,IDN.1.2_1,AronganLambalek,IDN.1.2.1_1
```

**The seeder derives `Levels.name` from the label half.** `1_Province`
creates a level literally called "Province", and that word then appears
throughout the app — in the administration picker, in role definitions, in
the generated bulk-upload template.

That is why `labels` is separate from `properties`. Writing the column as
`1_name` would create a tier named "name".

Labels usually cannot be guessed. GADM files carry `TYPE_<n>` / `ENGTYPE_<n>`
only for the deepest tier, so the suggestion cell fills in `Level 1`,
`Level 2` … as placeholders for the rest and expects you to replace them.

If a workspace already defines a tier, its existing name wins — the seeder
reuses `Levels` keyed on `(tenant, level)` and never renames one, because
roles and upload templates already reference it. The import reports when the
file disagrees.

---

## What the notebook checks

Every check mirrors a rule the seeder enforces, so a clean run means the
import will succeed.

| Step | Check |
|---|---|
| 1 | Property coverage — a property present on only *some* features cannot drive a level |
| 1 | Which values match `na_values` and will be blanked |
| 3 | Levels contiguous from 0; labels unique; no label spelled `Code` |
| 3 | Every mapped property actually exists in the file |
| 3 | No feature with a hole in its path — a blank tier above a non-blank one |
| 5 | Exactly one root value |
| 5 | Leaf names shared across parents (informational — handled correctly) |
| 5 | **Case-insensitive sibling collisions** (these silently merge — see below) |

Step 6 refuses to write if Step 3 found problems.

---

## Gotchas

**Names may have their spaces stripped.** The bundled Indonesia export
writes `AcehBarat`, `AronganLambalek`, `KawayXvi`. Setting
`split_camel_case: true` recovers `Aceh Barat`, but it is a guess, not a
restoration: `KawayXvi` becomes `Kaway Xvi` where the real name is
`Kaway XVI`. It is off by default because these strings become the labels
people read in the app, and a confidently wrong name is worse than an
unspaced one. Step 2 prints a sample so you can judge before committing.

**Case-insensitive siblings merge.** The seeder matches units on
`name__iexact` within a parent, so `SetiaBudi` and `Setiabudi` under the
same regency become one unit. Step 5 lists every such pair. In the bundled
Indonesia file there are two, which is why 6695 CSV rows produce 6693
level-3 units.

**Duplicate names across different parents are fine.** 273 sub-district
names in the Indonesia file appear under more than one parent — `Hutan`
under 14. The seeder keys on `(name, level, parent, tenant)`, so these stay
distinct. Step 5 reports the count as reassurance, not as a warning.

**`output` must be under `storage/`.** The backend container reads
`STORAGE_PATH`, which is bind-mounted from the repo's `storage/` directory,
and the seeder takes a storage-relative path. Step 6 prints the exact
`--source` value to use, or warns if the output landed somewhere the
container cannot see. `storage/.gitignore` ignores `*.csv`, so nothing you
generate can be committed by accident.

**Large files are slow to import, not to generate.** The notebook turns
6695 features into a CSV in about a second; the seeder takes ~35s for the
same file, because it walks each row parent-by-parent to keep units under
different parents distinct. That is a one-off cost per workspace.

---

## Adding another country

1. Drop the GeoJSON in `geojson/`.
2. Point `input` at it and `output` at `storage/administrations/<country>.csv`.
3. Run Step 1, paste the suggested block into `config.json`, replace the
   placeholder labels with the words that country actually uses
   (`Governorate`, `District`, `Ward`, …).
4. Run the rest. Fix anything Step 3 reports.
5. Import with `--dry-run` first.

Non-GADM sources work the same way — the suggestion cell only knows GADM's
conventions, but `properties` accepts any property names.

---

## Related

- `doc/design/SEED-002-administration-csv-seeder.md` — the CSV contract and
  the import rules
- `doc/design/SEED-001-fake-data-prefix-and-clean.md` — generating
  submissions once the hierarchy exists
