# Internal architecture

`prenatalppkt` is organized as a pipeline.

```text
raw ultrasound export
-> source extractor
-> section parsers
-> HPO and measurement mapping
-> Phenopacket builder
-> JSON output
```

The code is split so each layer has one job and can be tested on its own.

## Core layers

### 1. Source extraction

Main modules:

```text
src/prenatalppkt/etl/extractors/observer.py
src/prenatalppkt/etl/extractors/viewpoint_text.py
src/prenatalppkt/etl/extractors/viewpoint_hl7.py
```

The Observer extractor reads fetal measurements from Observer JSON. It returns
`TermBin` objects after mapping measurements through `TermBinFactory`.

Important calls:

```python
observer.extract(data)
observer.extract_all_fetuses(data)
observer.extract_from_file(path)
observer.extract_all_fetuses_from_file(path)
```

The ViewPoint HL7 extractor does not split segments itself. It reads them
through `src/prenatalppkt/etl/hl7_rows.py`, which turns every OBX segment into
a frozen `Hl7Row` (set id, value type, OBX-3 identifier and label, OBX-4
sub-id and fetus number, OBX-5 value, OBX-6 units, observation time, line
number) and raises `Hl7ParseError` naming the line when a segment is
malformed. New HL7 readers should start from these rows.

```python
from prenatalppkt.etl.hl7_rows import read_hl7_rows

rows = read_hl7_rows(text)
```

### 2. Scan typing

Main module:

```text
src/prenatalppkt/etl/scan_type.py
```

This layer distinguishes scan shapes.

Plain meaning:

> The extractor needs to know whether a fetus has first-trimester measurements,
> the full later-trimester biometry set, or an unsupported partial shape.

Important concepts:

- `ScanType`
- `classify_fetus()`
- `UnsupportedScanTypeError`

### 3. Clinical section parsers

Main package:

```text
src/prenatalppkt/etl/sections/
```

Important functions:

```python
parse_clinical_indication(data, source_format)
parse_pregnancy_dating(data, source_format)
parse_clinical_impression(data, source_format, hpo_cr=None)
parse_fetal_anatomy(data, source_format, hpo_cr=None)
parse_estimated_fetal_weight(data, source_format)
parse_fetal_ratios(data, source_format)
```

Each parser returns a dictionary. The dictionaries are simple on purpose:
they make notebook display, tests, and downstream assembly easier.

### 4. HPO loading and text recognition

Main package:

```text
src/prenatalppkt/hpo/
```

Important classes:

```python
HpoParser
HpoConceptRecognizer
FenominalConceptRecognizer
SimpleTerm
```

Current branch:

- `HpoParser` loads HPO.
- `HpoConceptRecognizer` is an abstract base class; `FenominalConceptRecognizer`
  is its one concrete implementation, wrapping fenominal.
- `get_hpo_concept_recognizer()` returns a `FenominalConceptRecognizer`.
- The recognizer returns `SimpleTerm` objects.

Fenominal branch:

- `get_hpo_concept_recognizer()` returns `FenominalConceptRecognizer`.
- Fenominal maps free text to HPO and carries negation as `excluded=True`.

### 5. Biometry mapping

Main files:

```text
src/prenatalppkt/data/mappings/biometry_hpo_mappings.yaml
src/prenatalppkt/mapping_loader.py
src/prenatalppkt/etl/term_bin_factory.py
src/prenatalppkt/measurements/percentile_range.py
src/prenatalppkt/measurements/term_bin.py
```

Important classes and methods:

```python
BiometryMappingLoader.load(path)
PercentileRange.contains(percentile)
PercentileRange.from_min_max(min, max)
TermBin.fits(percentile)
TermBinFactory.create_term_bin(...)
```

Plain meaning:

> This layer turns a percentile into HPO meaning.

### 6. Reference lookup

Main module:

```text
src/prenatalppkt/biometry_reference.py
```

Important class:

```python
FetalGrowthPercentiles
```

Important methods:

```python
lookup_percentile(measurement_type, gestational_age_weeks, value_mm)
lookup_zscore(measurement_type, gestational_age_weeks, value_mm)
```

Plain meaning:

> This layer reads INTERGROWTH-21st or NICHD reference tables and answers where
> a measurement falls.

### 7. Phenopacket assembly

Main module:

```text
src/prenatalppkt/builders/observer_phenopacket.py
```

Important public function:

```python
build_observer_phenopacket(data, hpo_parser, created_at, accession_id=None)
```

This function:

1. Extracts biometry by fetus.
2. Parses pregnancy dating, impression, anatomy, and EFW.
3. Builds Phenopacket `PhenotypicFeature` objects.
4. Marks normal-range biometry as excluded.
5. Adds HPO metadata.
6. Returns one Phenopacket per fetus.

### 8. Older high-level exporter

Main module:

```text
src/prenatalppkt/phenotypic_export.py
```

Important class:

```python
PhenotypicExporter
```

Important methods:

```python
evaluate_to_observation(...)
evaluate_and_export(...)
export_feature(...)
batch_export(...)
to_json(...)
```

This is an older helper for measurement evaluation and JSON export. The newer
Observer builder is the clearer path for Observer JSON to Phenopacket objects.

### 9. Genomics scaffold

Main package:

```text
src/prenatalppkt/genomics/
```

Important calls:

```python
scan_vcf_file(path)
build_vcf_file_entry(uri, attributes=None)
build_genomic_interpretation(variants, subject_id, interpretation_id)
```

This is structure only. It attaches VCF-derived variant loci to a Phenopacket,
but it is not a diagnosis engine.

## Tests as the architecture map

The tests mirror the code layers.

| Test area | What it proves |
|---|---|
| `tests/test_mapping_loader.py` | YAML mapping loads into objects |
| `tests/test_term_bin.py` | Percentile bins match correctly |
| `tests/etl/extractors/` | Source files are parsed correctly |
| `tests/etl/sections/` | Report sections parse independently |
| `tests/builders/` | Phenopacket assembly works |
| `tests/hpo/` | HPO loading and recognizers work |
| `tests/genomics/` | VCF scaffold works |
| `src/prenatalppkt/scripts/data_dict/tests/` | Data dictionary tools work |

## Design rules

Use these rules when changing internals.

1. Keep clinical mapping in YAML when possible.
2. Keep source parsing separate from Phenopacket assembly.
3. Keep raw measurements and interpreted HPO features separate.
4. Use tests to define behavior before refactoring.
5. Do not silently drop normal findings when they are meaningful as excluded
   Phenopacket features.

## Common pitfalls

### Normal does not mean omit

Normal-range biometry can still be emitted as an excluded Phenopacket feature.
That means the abnormality was considered and not observed.

### Observer and ViewPoint are sources, not output formats

The output should stay consistent even when the input source changes.

### The notebook is not the only implementation

The notebook is the readable demo. The reusable code lives in modules under
`src/prenatalppkt/`.

### The genomics code is a scaffold

The VCF code proves structure, not diagnosis.
