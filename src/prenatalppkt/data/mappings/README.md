# Mapping files

These two YAML files ship inside the installed package, so the converters
work the same from a wheel as from a clone. Code finds them through
`prenatalppkt.data_files.MAPPINGS_DIR`; nothing should build a path to them
from the repository root.

## `biometry_hpo_mappings.yaml`

What each biometry measurement means at each percentile. For every
measurement it holds the LOINC code of the raw value and a list of
percentile ranges, each with the HPO term to report and whether that range
counts as normal (a normal range is reported as an excluded term).

Read by `etl/term_bin_factory.py` (the converters), and by the older
`measurement_eval.py` and `phenotypic_export.py`.

## `measurement_registry.yaml`

Which measurements exist and what each export format calls them. For every
measurement it holds its role (required on second- and third-trimester
scans, first-trimester, or optional), its key in
`biometry_hpo_mappings.yaml` (or the reason it has none), and the label each
source uses: Observer, ViewPoint text, ViewPoint HL7, plus generic spellings.
Labels seen in a real export are kept apart from guessed ones.

Read once at import by `etl/measurement_registry.py`; the name tables and
required/optional lists in the ETL code are built from it.

## Why two files

The older `phenotypic_export.py` expects every top-level key in
`biometry_hpo_mappings.yaml` to carry percentile bins and fails on anything
else, so the registry's naming data lives in its own file.
