"""
test_mapping_loader.py - Tests for BiometryMappingLoader
"""

import pytest
from pathlib import Path
from prenatalppkt.mapping_loader import BiometryMappingLoader
from prenatalppkt.measurement_eval import DEFAULT_MAPPINGS_FILE


def test_load_mappings():
    """Test loading mappings from YAML."""
    yaml_path = DEFAULT_MAPPINGS_FILE

    if not yaml_path.exists():
        pytest.skip("YAML file not found")

    mappings = BiometryMappingLoader.load(yaml_path)

    # Check all measurement types present
    assert "head_circumference" in mappings
    assert "biparietal_diameter" in mappings
    assert "femur_length" in mappings
    assert "abdominal_circumference" in mappings
    assert "occipitofrontal_diameter" in mappings

    # Check HC has 8 bins
    hc_bins = mappings["head_circumference"]
    assert len(hc_bins) == 8

    # Check first bin structure
    first_bin = hc_bins[0]
    assert first_bin.hpo_id == "HP:0000252"
    assert first_bin.hpo_label == "Microcephaly"
    assert first_bin.normal is False


def test_load_nonexistent_file():
    """Test error handling for missing file."""
    with pytest.raises(FileNotFoundError):
        BiometryMappingLoader.load(Path("nonexistent.yaml"))


def test_loinc_propagates_to_bins(tmp_path):
    """A measurement with a `loinc:` block stamps every bin with that LOINC."""
    yaml_text = """\
head_circumference:
  loinc:
    id: "LOINC:11984-2"
    label: "Fetal Head Circumference US"
  bins:
    - min: 50
      max: 90
      id: "HP:0000240"
      label: "Abnormality of skull size"
      normal: true
    - min: 97
      max: 100
      id: "HP:0000256"
      label: "Macrocephaly"
      normal: false
"""
    p = tmp_path / "m.yaml"
    p.write_text(yaml_text, encoding="utf-8")

    mappings = BiometryMappingLoader.load(p)
    bins = mappings["head_circumference"]
    assert len(bins) == 2
    assert all(b.loinc_code == "LOINC:11984-2" for b in bins)
    assert all(b.loinc_label == "Fetal Head Circumference US" for b in bins)


def test_legacy_list_shape_still_supported(tmp_path):
    """Top-level entries that are plain lists (no `loinc:` block) still load."""
    yaml_text = """\
occipitofrontal_diameter:
  - min: 50
    max: 90
    id: "HP:0000240"
    label: "Abnormality of skull size"
    normal: true
"""
    p = tmp_path / "m.yaml"
    p.write_text(yaml_text, encoding="utf-8")

    mappings = BiometryMappingLoader.load(p)
    bins = mappings["occipitofrontal_diameter"]
    assert len(bins) == 1
    assert bins[0].loinc_code is None
    assert bins[0].loinc_label is None


def test_bundled_yaml_has_loinc_for_four_core_measurements():
    """The shipped YAML carries verified LOINC codes for HC/BPD/AC/FL."""
    yaml_path = DEFAULT_MAPPINGS_FILE
    if not yaml_path.exists():
        pytest.skip("YAML file not found")

    mappings = BiometryMappingLoader.load(yaml_path)
    expected = {
        "head_circumference": "LOINC:11984-2",
        "biparietal_diameter": "LOINC:11820-8",
        "abdominal_circumference": "LOINC:11979-2",
        "femur_length": "LOINC:11963-6",
    }
    for measurement_type, expected_code in expected.items():
        bins = mappings[measurement_type]
        assert bins, f"no bins loaded for {measurement_type}"
        assert all(b.loinc_code == expected_code for b in bins), (
            f"{measurement_type} bins missing LOINC {expected_code}"
        )
