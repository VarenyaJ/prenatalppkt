# Reference

This section is the quick lookup map for `prenatalppkt`.

Use it when you need to answer:

- Which module owns this behavior?
- Which class or function should I call?
- Which enum or config file defines this value?
- Which tests prove the behavior?

## Main building blocks

| Block | Main module | What it does |
|---|---|---|
| HPO loading | `prenatalppkt.hpo.hpo_parser` | Loads HPO and returns a concept recognizer |
| HPO term object | `prenatalppkt.hpo.simple_term` | Carries HPO id, label, excluded flag, and optional gestational age |
| Gestational age | `prenatalppkt.gestational_age` | Stores completed weeks and days |
| Observer extraction | `prenatalppkt.etl.extractors.observer` | Reads Observer JSON measurements |
| ViewPoint text extraction | `prenatalppkt.etl.extractors.viewpoint_text` | Reads ViewPoint text biometry |
| ViewPoint HL7 extraction | `prenatalppkt.etl.extractors.viewpoint_hl7` | Reads ViewPoint HL7 OBX biometry |
| HL7 row reading | `prenatalppkt.etl.hl7_rows` | Splits every OBX segment of a ViewPoint HL7 export into a typed row |
| Section parsing | `prenatalppkt.etl.sections` | Reads non-biometry report sections |
| Scan typing | `prenatalppkt.etl.scan_type` | Classifies first-trimester, T2/T3, and unknown scan shapes |
| Mapping loader | `prenatalppkt.mapping_loader` | Loads YAML HPO mapping rules |
| Mapping factory | `prenatalppkt.etl.term_bin_factory` | Creates mapped `TermBin` objects |
| Reference lookup | `prenatalppkt.biometry_reference` | Looks up percentiles and z-scores |
| Observer builder | `prenatalppkt.builders.observer_phenopacket` | Builds Phenopacket objects from Observer JSON |
| Older exporter | `prenatalppkt.phenotypic_export` | Evaluates measurements and writes JSON dictionaries |
| Genomics scaffold | `prenatalppkt.genomics` | Scans VCFs and builds Phenopacket genomic scaffold objects |
| Data dictionary | `prenatalppkt.scripts.data_dict` | Inventories source fields and cross-source concepts |

## Core call path

```text
Observer JSON
-> observer.extract_all_fetuses()
-> TermBinFactory.create_term_bin()
-> parse_pregnancy_dating()
-> parse_clinical_impression()
-> parse_fetal_anatomy()
-> build_observer_phenopacket()
-> phenopackets.schema.v2.Phenopacket
```

## Most useful imports

```python
from prenatalppkt.builders import build_observer_phenopacket
from prenatalppkt.etl.extractors import observer
from prenatalppkt.etl.sections import (
    parse_clinical_indication,
    parse_pregnancy_dating,
    parse_clinical_impression,
    parse_fetal_anatomy,
    parse_estimated_fetal_weight,
    parse_fetal_ratios,
)
from prenatalppkt.hpo import HpoParser, SimpleTerm
from prenatalppkt.gestational_age import GestationalAge
```

## Tests to start with

| Behavior | Test file |
|---|---|
| Observer extraction | `tests/etl/extractors/test_observer.py` |
| Multi-fetus Observer extraction | `tests/etl/extractors/test_observer_multifetus.py` |
| Scan typing | `tests/etl/test_scan_type.py` |
| YAML HPO mapping | `tests/test_mapping_loader.py` |
| Term bin behavior | `tests/test_term_bin.py` |
| Section parsers | `tests/etl/sections/` |
| Phenopacket builder | `tests/builders/test_observer_phenopacket.py` |
| HPO parser and recognizer | `tests/hpo/` |
| Genomics scaffold | `tests/genomics/` |

