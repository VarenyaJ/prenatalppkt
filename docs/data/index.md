# Data

`prenatalppkt` works with three kinds of data:

1. Ultrasound source files.
2. Fetal growth reference tables.
3. Clinical mapping files.

These are kept separate so the code can parse source data, compare or use
percentiles, and map results to HPO terms without mixing those jobs together.

## Source data

The main working source is Observer JSON.

Fixture examples live in:

```text
tests/data/
```

Useful examples:

| File | Use |
|---|---|
| `Apple_Sally_pretty.json` | Observer JSON fixture used in end-to-end tests |
| `Blue_Sally_pretty.json` | Additional Observer fixture |
| `Charm_Sally_pretty.json` | Additional Observer fixture |
| `Diva_Sally_pretty.json` | First-trimester-style fixture |
| `Eclair_Sally_pretty.json` | Additional Observer fixture |
| `viewpoint_text_test.txt` | ViewPoint text parser fixture |
| `viewpoint_hl7_test.txt` | ViewPoint HL7 parser fixture |
| `hp.json.gz` | Compressed HPO fixture used in tests |
| `Apple_Sally.vcf` | Synthetic VCF fixture for genomics scaffold tests |

The fixtures are part of the test contract. If a parser changes, the tests
show whether expected behavior changed.

## Observer JSON

Observer JSON files can contain one or more fetus blocks.

The extractor looks for:

- fetus number
- biometric measurements
- calculated percentile
- calculated gestational age
- anatomy text
- clinical impression
- estimated fetal weight
- fetal ratios

The main extractor is:

```python
from prenatalppkt.etl.extractors import observer

term_bins = observer.extract(observer_data)
all_fetuses = observer.extract_all_fetuses(observer_data)
```

Use `extract()` for the older first-fetus path. Use `extract_all_fetuses()` when
the input may contain twins or higher-order pregnancies.

## ViewPoint data

ViewPoint support is present but less complete than Observer support.

Relevant modules:

```text
src/prenatalppkt/etl/extractors/viewpoint_text.py
src/prenatalppkt/etl/extractors/viewpoint_hl7.py
src/prenatalppkt/parser/viewpoint/
```

The goal is to parse ViewPoint text and HL7 into the same clinical concepts
used by the Observer path.

## Reference data

Reference tables live under:

```text
data/raw/
data/parsed/
```

Supported sources:

- INTERGROWTH-21st
- NICHD

The main class is:

```python
from prenatalppkt.biometry_reference import FetalGrowthPercentiles
```

Important methods:

```python
reference = FetalGrowthPercentiles(source="intergrowth")
percentile = reference.lookup_percentile(measurement_type, ga_weeks, value_mm)
zscore = reference.lookup_zscore(measurement_type, ga_weeks, value_mm)
```

Plain meaning:

> The reference layer answers where a fetal measurement falls compared with a
> reference table.

## Mapping data

The main clinical mapping file is:

```text
src/prenatalppkt/data/mappings/biometry_hpo_mappings.yaml
```

It maps:

```text
measurement type
-> LOINC code for the raw measurement
-> percentile bin
-> HPO term
-> normal or abnormal flag
```

Example idea:

```text
head circumference below 3rd percentile
-> HP:0000252
-> Microcephaly
-> normal: false
```

Normal bins are intentionally included. They become excluded Phenopacket
features, which means the abnormality was considered and not observed.

## Mapping loader

The loader turns YAML into Python objects:

```python
from prenatalppkt.mapping_loader import BiometryMappingLoader

mappings = BiometryMappingLoader.load(path)
```

The returned mappings contain `TermBin` objects.

## `TermBin`

`TermBin` is the mapped measurement object.

It stores:

- percentile range
- HPO id
- HPO label
- normal flag
- description
- LOINC code and label
- raw value in millimeters
- gestational age

Important methods:

```python
term_bin.fits(percentile)
term_bin.to_measurement_dict()
```

Plain meaning:

> A `TermBin` says which HPO term belongs to a measurement percentile bin.

## Data preparation scripts

Reference table parsing scripts live in:

```text
src/prenatalppkt/scripts/
```

Examples:

```text
parse_intergrowth_txt_all.py
parse_intergrowth_docling_all.py
parse_nichd_raw.py
normalize_tsv_to_csv.py
```

These scripts prepare reference data. They are not the main runtime pipeline.

## Data dictionary

The data dictionary scripts live in:

```text
src/prenatalppkt/scripts/data_dict/
```

They inventory source-system fields and help relate Observer and ViewPoint
fields to clinical concepts.

Important files:

| File | Use |
|---|---|
| `concept_aliases.yaml` | Cross-source concept equivalence |
| `clusters.yaml` | Clinician-readable field groupings |
| `extract_all.py` | Build data dictionary rows |
| `render_readme.py` | Render Markdown docs |
