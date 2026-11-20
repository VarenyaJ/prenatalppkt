# prenatalppkt

`prenatalppkt` is a Python library for turning prenatal ultrasound data into
GA4GH Phenopacket v2 records.

It focuses on:

- parsing prenatal ultrasound exports
- preserving gestational-age context
- mapping biometry percentiles to HPO terms
- representing normal findings as excluded Phenopacket features
- carrying raw measurements with LOINC metadata when possible
- building Phenopacket objects that can later connect to genomic data

## Pipeline

```text
raw ultrasound export
-> extract measurements and report sections
-> map biometry percentiles to HPO terms
-> preserve raw LOINC-coded measurements
-> build GA4GH Phenopacket v2 objects
```

## Start here

If you are installing or testing the package, start with [](setup.md).

If you want the main architecture, read [](internal.md).

If you want exact functions, classes, enums, and config files, use the
[](reference/index.md).

```{toctree}
:maxdepth: 2
:caption: User guide

setup
data/index
measurements
prenatal-skeletal-terms
known-limitations
internal
```

```{toctree}
:maxdepth: 2
:caption: Measurement pages

measurement/head_circumference
measurement/biparietal_diameter
measurement/abdominal_circumference
measurement/femur_length
measurement/occipitofrontal_diameter
```

```{toctree}
:maxdepth: 2
:caption: Data

data/reference_data
data/fetal_growth_methods
data/exomiser-input-shape
data_dictionary/README
data_dictionary/schema
data_dictionary/clusters
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/index
reference/building_blocks
reference/functions
reference/enums-config
api/prenatalppkt
```
