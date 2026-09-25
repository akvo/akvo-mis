# plan.json — the contract between analysis and the scripts

The `//` comments below are explanations only; plan.json itself must be plain
JSON. `render_plan.py` checks it against the data and renders `plan.md` for the
user; `mis.py` executes it. Paths in `file` are relative to plan.json.

```jsonc
{
  "workspace": {
    "subdomain": "kenyawater",            // lowercase a-z 0-9 -, max 63
    "base_domain": "mis.akvotest.org",    // or mis.akvo.org (production);
                                          // mis.py refuses any other domain
    "scheme": "https",                    // required; http only for the local
                                          // stack via --connect http://localhost:8000
    "email": "person@org.org",            // becomes the workspace super admin
    "first_name": "Ana", "last_name": "Silva"
  },
  "administration": {
    "levels": ["Country", "Region", "District"],   // [0] is the root's level
    "root": "Kenya",                               // the single level-0 unit
    "source": {"file": "data.xlsx", "sheet": "Water points",
               "columns": ["Region", "District"]}, // one column per level 1..n
    "sources": [],            // optional: more {file, sheet, columns}
    "units": [["Coast", "Kwale"]],   // optional: extra paths below the root
    "aliases": {"CENTRAL": "Central"} // spelling fixes, applied everywhere
  },
  "forms": [
    {"key": "water_point", "name": "Water Point", "type": "registration",
     "description": "One record per water point.",
     "groups": [{"label": "Identification", "questions": [
       {"name": "wp_code", "label": "Water point ID", "type": "input",
        "required": true, "meta": true},
       {"name": "location", "label": "Location", "type": "administration",
        "required": true},
       {"name": "gps", "label": "GPS location", "type": "geo"},
       {"name": "wp_type", "label": "Type", "type": "option",
        "options": ["Borehole", "Piped tap"]},
       {"name": "households", "label": "Households served", "type": "number",
        "min": 0, "max": 5000, "decimal": false},
       {"name": "reason", "label": "Why?", "type": "text",
        "depends_on": {"question": "wp_type", "values": ["Borehole"]}}
     ]}]},
    {"key": "visit", "name": "Monthly Visit", "type": "monitoring",
     "parent": "water_point", "groups": ["..."]}
  ],
  "data": [
    {"form": "water_point", "file": "data.xlsx", "sheet": "Water points", // sheet: xlsx only
     "key_columns": ["Water Point ID"],             // stable id per record
     "administration_columns": ["Region", "District"],
     "geo": {"lat": "Latitude", "lng": "Longitude"}, // or {"column": "GPS"}
     "columns": {"wp_code": "Water Point ID", "wp_type": "Type"},
     "value_maps": {"wp_type": {"BH": "Borehole", "None": ""}},
                                 // raw -> option label; "" = no answer
     "date_format": "%d/%m/%Y",  // needed when dates are 03/04/2026-style
     "multi_separator": "[;,|/]",                    // regex, multiple_option
     "unmapped_columns": ["Remarks"]},               // shown as "not loaded"
    {"form": "visit", "file": "data.xlsx", "sheet": "Monthly visits",
     "parent": {"form": "water_point", "key_columns": ["Water Point ID"]},
     "key_columns": ["Water Point ID", "Visit date"],
     "columns": {"visit_date": "Visit date"}}
  ],
  "notes": ["Decisions the user should see, in plain words."]
}
```

## Question types

| plan `type` | MIS | answer taken from the cell as |
|---|---|---|
| `input` / `text` | short / long text | trimmed string |
| `number` | number (`min`, `max`, `decimal`) | number; `1,200` and `12 kg` are cleaned |
| `date` | date | `YYYY-MM-DD`. Excel dates and ISO text parse; `dd/mm` or `mm/dd` text needs `date_format` |
| `option` | pick one | matched to an option label, case-insensitive, after `value_maps` |
| `multiple_option` | pick several | split on `multi_separator`, each part matched |
| `geo` | GPS point | Set `geo` on the data spec, either `{lat, lng}` columns or `{column}` holding `"lat, lng"`. There is no need to also map it in `columns`. |
| `administration` | cascade over the hierarchy | the row's `administration_columns` path |
| `photo` / `signature` / `attachment` | media | not loadable from a spreadsheet; field-only |

## Rules the scripts rely on

- Registration forms: exactly one `administration` question and at least one
  `meta: true` question (the datapoint name is the meta answers joined by
  " - "). Monitoring forms need neither, because they inherit the parent's
  administration, geo and name.
- `name` is a machine name: lowercase, unique in the form, never renamed after
  loading. `depends_on` may only point at an **earlier** `option` question.
- `key_columns` is required and must identify a row. On registration data it
  becomes the record's uuid, and monitoring rows find their parent through
  it. On monitoring data it makes reruns safe, so include the date column.
  Rows with a blank key are skipped; of rows sharing a key, only the first
  is loaded.
- Option labels are what enumerators see. Stored values are derived from the
  labels (`Piped tap` → `piped_tap`), so don't rename options after loading.
  Two labels that simplify to the same value (`A/B` and `A B`) are rejected;
  the same goes for group labels within a form.
- CSV files: the delimiter is detected; set `"sep": ";"` in the data spec
  to force one.
- Any column you leave out of `columns` is not loaded. List it in
  `unmapped_columns` so the user sees what is dropped.
- Cells are read as text exactly as written. `None`, `NA` and `-` are **not**
  treated as blank; only empty cells are. Use `value_maps` to say what they mean.
- `aliases` and `value_maps` keys match ignoring case and surrounding
  spaces, so `"govt": "Government"` also covers `Govt` and ` GOVT `.
- In `load-data --dry-run` payloads, `administration` is `-1` and question
  ids are question names. The real ids exist only once the workspace is seeded.
