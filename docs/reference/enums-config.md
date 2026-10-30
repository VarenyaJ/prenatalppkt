# Enums, constants, and config

This page lists the named values that shape the pipeline.

## Biometry measurement enum

Module:

```text
prenatalppkt.etl.constants
```

Enum:

```text
BiometryMeasurement
```

Members:

| Member | Value |
|---|---|
| `HEAD_CIRCUMFERENCE` | `HC` |
| `BIPARIETAL_DIAMETER` | `BPD` |
| `ABDOMINAL_CIRCUMFERENCE` | `AC` |
| `FEMUR_LENGTH` | `Femur` |
| `NUCHAL_FOLD` | `Nuchal Fold` |
| `CEREBELLUM` | `Cerebellum` |
| `OCCIPITOFRONTAL_DIAMETER` | `OFD` |
| `HUMERUS_LENGTH` | `Humerus` |
| `CROWN_RUMP_LENGTH` | `CRL` |
| `NUCHAL_TRANSLUCENCY` | `NT` |
| `TIBIA_LENGTH` | `Tibia` |
| `FIBULA_LENGTH` | `Fibula` |
| `RADIUS_LENGTH` | `Radius` |
| `ULNA_LENGTH` | `Ulna` |
| `FOOT_LENGTH` | `Foot` |
| `CISTERNA_MAGNA` | `Cisterna Magna` |
| `NASAL_BONE` | `Nasal Bone` |
| `LATERAL_VENTRICLE_LEFT` | `Lateral Vent left` |
| `LATERAL_VENTRICLE_RIGHT` | `Lateral Vent right` |
| `BIORBITAL_DIAMETER` | `Biorbit` |
| `MEAN_GESTATIONAL_SAC` | `Mean Gest Sac` |

Methods:

| Method | Meaning |
|---|---|
| `from_string(s)` | Convert standard string to enum member |
| `all_values()` | Return all standard measurement strings |

## Biometry type enum

Module:

```text
prenatalppkt.biometry_type
```

Enum:

```text
BiometryType
```

Members:

| Member | Value |
|---|---|
| `HEAD_CIRCUMFERENCE` | `head_circumference` |
| `BIPARIETAL_DIAMETER` | `biparietal_diameter` |
| `ABDOMINAL_CIRCUMFERENCE` | `abdominal_circumference` |
| `FEMUR_LENGTH` | `femur_length` |
| `OCCIPITOFRONTAL_DIAMETER` | `occipitofrontal_diameter` |
| `ESTIMATED_FETAL_WEIGHT` | `estimated_fetal_weight` |

## Scan type enum

Module:

```text
prenatalppkt.etl.scan_type
```

Enum:

```text
ScanType
```

Members:

| Member | Value | Meaning |
|---|---|---|
| `FIRST_TRIMESTER` | `first_trimester` | CRL/NT style scan |
| `T2_T3_BIOMETRY` | `t2_t3_biometry` | Full HC/BPD/AC/Femur biometry |
| `UNKNOWN` | `unknown` | Partial or unsupported shape |

Constants:

| Constant | Value |
|---|---|
| `T1_LABELS` | `CRL`, `NT` |
| `T2T3_REQUIRED_LABELS` | `AC`, `BPD`, `HC`, `Femur` |

## Section header enum

Module:

```text
prenatalppkt.etl.constants
```

Enum:

```text
SectionHeader
```

Selected members:

| Member | Value |
|---|---|
| `CLINICAL_IMPRESSION` | `Impression` |
| `CLINICAL_INDICATIONS` | `Indication` |
| `PREGNANCY` | `Pregnancy` |
| `PREGNANCY_PROGRESSION` | `Dating` |
| `FETAL_BIOMETRY` | `Fetal Biometry` |
| `FETAL_ANATOMY` | `Fetal Anatomy` |
| `FETAL_ECHO` | `Fetal Echocardiogram` |
| `FETAL_DOPPLER` | `Fetal Doppler` |

Method:

| Method | Meaning |
|---|---|
| `from_string(s)` | Convert section title to enum member |

## Name maps

Module:

```text
prenatalppkt.etl.constants
```

| Map | Use |
|---|---|
| `OBSERVER_NAME_MAP` | Maps Observer labels to `BiometryMeasurement` |
| `VIEWPOINT_TEXT_NAME_MAP` | Maps ViewPoint text labels to `BiometryMeasurement` |
| `VIEWPOINT_HL7_NAME_MAP` | Maps ViewPoint HL7 names to `BiometryMeasurement` |
| `GENERIC_NAME_MAP` | Catches common label variations |

These maps let different source systems feed the same standard measurement
names.

## HPO mapping config

File:

```text
src/prenatalppkt/data/mappings/biometry_hpo_mappings.yaml
```

Shape:

```yaml
head_circumference:
  loinc:
    id: "LOINC:11984-2"
    label: "Fetal Head Circumference US"
  bins:
    - min: 0
      max: 3
      id: "HP:0000252"
      label: "Microcephaly"
      normal: false
```

Each measurement entry can contain:

| Field | Meaning |
|---|---|
| `loinc.id` | LOINC code for the raw measurement |
| `loinc.label` | LOINC label |
| `bins` | List of percentile-to-HPO rules |
| `min` | Lower percentile bound |
| `max` | Upper percentile bound |
| `id` | HPO id |
| `label` | HPO label |
| `normal` | Whether the bin means normal range |

## Reference-data constants

Module:

```text
prenatalppkt.biometry_reference
```

| Name | Meaning |
|---|---|
| `RESOURCES_DIR` | Parsed reference data directory |
| `SUPPORTED_MEASURES` | Supported measurement keys and labels |
| `SHORT_ALIASES` | Short names for INTERGROWTH filenames |
| `MEASURE_NAME_ALIASES` | Name cleanup for reference tables |

## Data dictionary config

Directory:

```text
src/prenatalppkt/scripts/data_dict/
```

| File | Meaning |
|---|---|
| `concept_aliases.yaml` | Cross-source concept equivalence |
| `clusters.yaml` | Clinician-readable groupings |
