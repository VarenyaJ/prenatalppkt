"""
Tests for Observer JSON extractor.
"""

import json
from pathlib import Path
from typing import ClassVar

import pytest

from prenatalppkt.etl.extractors import observer
from prenatalppkt.etl.term_bin_factory import TermBinFactory
from prenatalppkt.measurements.term_bin import TermBin

DATA_DIR = Path(__file__).resolve().parents[3] / "tests" / "data"


class TestObserverExtract:
    """Tests for extract() function."""

    def test_extract_basic(self):
        """Test extraction with minimal valid data."""
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                            "calculated_ega": 25.5,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                            "calculated_ega": 26.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                            "calculated_ega": 25.8,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                            "calculated_ega": 26.1,
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)

        assert len(term_bins) == 4
        assert all(isinstance(tb, TermBin) for tb in term_bins)

        # Check HC conversion from cm to mm
        hc_bin = next(tb for tb in term_bins if "HC" in tb.description)
        assert hc_bin is not None
        # 17.5 cm = 175 mm
        assert "175" in hc_bin.description or "175.0" in hc_bin.description

    def test_extract_with_custom_factory(self):
        """Test extraction with custom factory."""
        factory = TermBinFactory()
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data, factory)
        assert len(term_bins) == 4

    def test_extract_missing_fetuses_key(self):
        """Test extraction with missing 'fetuses' key."""
        data = {"exam": {}, "patient": {}}  # noqa: F841

        with pytest.raises(ValueError, match="Missing 'fetuses' key"):
            observer.extract(data)

    def test_extract_empty_fetuses(self):
        """Test extraction with empty fetuses list."""
        data = {"fetuses": []}  # noqa: F841

        with pytest.raises(ValueError, match="non-empty list"):
            observer.extract(data)

    def test_extract_invalid_type(self):
        """Test extraction with invalid data type."""
        with pytest.raises(ValueError, match="Expected dict"):
            observer.extract("not a dict")

    def test_extract_missing_required_measurements_still_returns_what_it_has(self):
        """A fetus with only some of HC/BPD/AC/Femur - a targeted follow-up
        scan, not a full anatomy survey - still returns whatever is present
        and mappable, rather than raising."""
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        }
                        # Missing BPD, AC, Femur
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)
        assert len(term_bins) == 1
        assert term_bins[0].description.startswith("HC:")

    def test_extract_no_measurements_at_all_raises(self):
        """A fetus with an empty measurements list still raises - there is
        nothing to extract, unlike a partial-but-real targeted scan."""
        data = {  # noqa: F841
            "fetuses": [{"fetus": {"fetus_number": 1}, "measurements": []}]
        }

        with pytest.raises(ValueError, match="No measurements present"):
            observer.extract(data)

    def test_extract_skips_measurements_without_percentile(self):
        """Test that measurements without percentiles are skipped."""
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                        },
                        {
                            "label": "Nuchal Fold",
                            "value": 4.5,
                            "unit_of_measure": "mm",
                            # No percentile - should be skipped
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)
        # Should have 4 (not 5) since Nuchal Fold has no percentile
        assert len(term_bins) == 4

    def test_extract_optional_measurements(self):
        """Optional measurements with a real percentile produce bins."""
        data = {
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": _required_with_display()
                    + [
                        {
                            "label": "Nuchal Fold",
                            "value": 4.5,
                            "unit_of_measure": "mm",
                            "calculated_percentile": 10.0,
                            "percentile_for_display": "10%",
                        },
                        {
                            "label": "Cerebellum",
                            "value": 25.0,
                            "unit_of_measure": "mm",
                            "calculated_percentile": 45.0,
                            "percentile_for_display": "45%",
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)

        names = {tb.description.split(":")[0] for tb in term_bins}
        assert names == {"HC", "BPD", "AC", "Femur", "Nuchal Fold", "Cerebellum"}


class TestObserverExtractFromFile:
    """Tests for extract_from_file() function."""

    def test_extract_from_file_not_found(self):
        """Test extraction from non-existent file."""
        with pytest.raises(FileNotFoundError):
            observer.extract_from_file(Path("nonexistent.json"))

    def test_extract_from_file_invalid_json(self, tmp_path):
        """Test extraction from file with invalid JSON."""
        test_file = tmp_path / "invalid.json"
        test_file.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            observer.extract_from_file(test_file)

    def test_extract_from_file_success(self, tmp_path):
        """Test successful extraction from file."""
        test_file = tmp_path / "valid.json"
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                        },
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        term_bins = observer.extract_from_file(test_file)
        assert len(term_bins) == 4


class TestObserverUnitConversion:
    """Tests for unit conversion."""

    def test_convert_cm_to_mm(self):
        """Test centimeter to millimeter conversion."""
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)

        # All values should be converted to mm (x10)
        hc = next(tb for tb in term_bins if "HC" in tb.description)
        assert "175" in hc.description  # 17.5 * 10

    def test_nuchal_fold_mm_no_conversion(self):
        """Test that mm values are not converted."""
        data = {  # noqa: F841
            "fetuses": [
                {
                    "fetus": {"fetus_number": 1},
                    "measurements": [
                        {
                            "label": "HC",
                            "value": 17.5,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 50.0,
                        },
                        {
                            "label": "BPD",
                            "value": 6.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 55.0,
                        },
                        {
                            "label": "AC",
                            "value": 21.2,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 48.0,
                        },
                        {
                            "label": "Femur",
                            "value": 4.8,
                            "unit_of_measure": "cm",
                            "calculated_percentile": 52.0,
                        },
                        {
                            "label": "Nuchal Fold",
                            "value": 4.5,
                            "unit_of_measure": "mm",
                            "calculated_percentile": 10.0,
                        },
                    ],
                }
            ]
        }

        term_bins = observer.extract(data)

        assert len(term_bins) == 5
        nf = next(tb for tb in term_bins if tb.description.startswith("Nuchal Fold"))
        assert nf.value_mm == 4.5  # already mm, no conversion


# ---------------------------------------------------------------------------
# First-trimester (T1) dispatch through the same observer.extract() entry point.
# ---------------------------------------------------------------------------


def _t1_fixture(*measurements: dict) -> dict:
    return {
        "fetuses": [{"fetus": {"fetus_number": 1}, "measurements": list(measurements)}]
    }


_CRL_OK = {
    "label": "CRL",
    "value": 45.0,
    "unit_of_measure": "mm",
    "calculated_percentile": 50.0,
    "calculated_ega": 11.3,
}

_NT_OK = {
    "label": "NT",
    "value": 2.0,
    "unit_of_measure": "mm",
    "calculated_percentile": 50.0,
    "calculated_ega": 11.3,
}

_NT_ELEVATED = {
    "label": "NT",
    "value": 4.2,
    "unit_of_measure": "mm",
    "calculated_percentile": 96.0,
    "calculated_ega": 12.0,
}


class TestObserverT1:
    """T1 path through observer.extract() (unified entry, dispatches on scan type)."""

    def test_crl_only_returns_one_bin(self):
        bins = observer.extract(_t1_fixture(_CRL_OK))
        assert len(bins) == 1
        assert isinstance(bins[0], TermBin)
        # CRL at 50% lands in the normal-range HP:0001507 bin.
        assert bins[0].hpo_id == "HP:0001507"
        assert bins[0].normal is True

    def test_nt_only_returns_one_bin(self):
        bins = observer.extract(_t1_fixture(_NT_OK))
        assert len(bins) == 1
        assert bins[0].hpo_id == "HP:0010880"

    def test_both_crl_and_nt_returns_two_bins(self):
        bins = observer.extract(_t1_fixture(_CRL_OK, _NT_ELEVATED))
        assert len(bins) == 2
        ids = {b.hpo_id for b in bins}
        assert ids == {"HP:0001507", "HP:0010880"}
        nt_bin = next(b for b in bins if b.hpo_id == "HP:0010880")
        assert nt_bin.normal is False

    def test_skips_crl_without_percentile_but_keeps_nt(self):
        crl_no_pct = {**_CRL_OK}
        del crl_no_pct["calculated_percentile"]
        bins = observer.extract(_t1_fixture(crl_no_pct, _NT_OK))
        assert len(bins) == 1
        assert bins[0].hpo_id == "HP:0010880"

    def test_t1_classified_but_nothing_parseable_raises(self):
        # CRL + NT labels classify the fetus FIRST_TRIMESTER, but with both
        # percentiles missing neither parses, so _parse_t1_measurements returns
        # [] and extract() raises rather than handing back an empty bin list.
        crl_no_pct = {**_CRL_OK}
        del crl_no_pct["calculated_percentile"]
        nt_no_pct = {**_NT_OK}
        del nt_no_pct["calculated_percentile"]
        with pytest.raises(
            observer.UnsupportedScanTypeError, match="no CRL or NT measurement parsed"
        ):
            observer.extract(_t1_fixture(crl_no_pct, nt_no_pct))

    def test_diva_sally_crl_not_calculated_raises(self):
        # Diva is the only T1 fixture, and its sole measurement (CRL) is
        # exported as percentile 0 with empty display text - Observer's "not
        # calculated" placeholder - so nothing parses and the T1 path raises.
        path = DATA_DIR / "Diva_Sally_pretty.json"
        with pytest.raises(
            observer.UnsupportedScanTypeError, match="no CRL or NT measurement parsed"
        ):
            observer.extract_from_file(path)


def _required_with_display() -> list[dict]:
    """HC/BPD/AC/Femur with real percentiles and their display text."""
    return [
        {
            "label": label,
            "value": value,
            "unit_of_measure": "cm",
            "calculated_percentile": pct,
            "percentile_for_display": f"{round(pct)}%",
        }
        for label, value, pct in [
            ("HC", 25.0, 42.5),
            ("BPD", 6.68, 51.2),
            ("AC", 22.62, 55.6),
            ("Femur", 5.01, 46.8),
        ]
    ]


def _not_calculated(label: str, value: float = 4.0) -> dict:
    """A measurement in the exact shape Observer exports when it has no
    growth chart for it: percentile 0 with empty display text."""
    return {
        "label": label,
        "value": value,
        "unit_of_measure": "mm",
        "calculated_percentile": 0,
        "percentile_for_display": "",
    }


class TestObserverPercentileNotCalculated:
    """Observer's "0 with empty display" placeholder is never read as a real
    0th-percentile result, on either the T2/T3 or the T1 path."""

    @pytest.mark.parametrize("label", ["OFD", "Tibia", "HC"])
    def test_t2t3_placeholder_is_skipped(self, label):
        measurements = [m for m in _required_with_display() if m["label"] != label] + [
            _not_calculated(label)
        ]
        bins = observer.extract(
            {"fetuses": [{"fetus": {"fetus_number": 1}, "measurements": measurements}]}
        )
        names = {b.description.split(":")[0].strip() for b in bins}
        assert label not in names

    def test_t1_nt_placeholder_is_skipped_crl_kept(self):
        bins = observer.extract(_t1_fixture(_CRL_OK, _not_calculated("NT", 1.8)))
        assert [b.description.split(":")[0] for b in bins] == ["CRL"]

    def test_t1_crl_placeholder_is_skipped_nt_kept(self):
        bins = observer.extract(_t1_fixture(_not_calculated("CRL", 45.0), _NT_OK))
        assert [b.description.split(":")[0] for b in bins] == ["NT"]

    def test_t1_only_placeholders_raises(self):
        with pytest.raises(
            observer.UnsupportedScanTypeError, match="no CRL or NT measurement parsed"
        ):
            observer.extract(
                _t1_fixture(_not_calculated("CRL", 45.0), _not_calculated("NT", 1.8))
            )

    @pytest.mark.parametrize(
        "percentile,display",
        [
            (0, "<1%"),  # zero, but with display text
            (0.1, "<1%"),  # real low reading
            (0.1, ""),  # non-zero, empty display
        ],
    )
    def test_real_low_readings_are_kept(self, percentile, display):
        nt = {
            **_NT_OK,
            "calculated_percentile": percentile,
            "percentile_for_display": display,
        }
        bins = observer.extract(_t1_fixture(nt))
        assert len(bins) == 1

    def test_zero_without_display_key_is_kept(self):
        # No percentile_for_display key at all: not the placeholder shape.
        nt = {**_NT_OK, "calculated_percentile": 0}
        assert "percentile_for_display" not in nt
        bins = observer.extract(_t1_fixture(nt))
        assert len(bins) == 1


class TestObserverCorpus:
    """extract_from_file() end-to-end over every shipped Observer fixture.

    Keyed on bin count + the set of measurements flagged abnormal, not on
    specific HPO IDs, so scaffold T1 mappings can be finalised without churn.
    """

    EXPECTED: ClassVar[dict[str, tuple[int, set[str]]]] = {
        "Apple_Sally_pretty.json": (4, set()),
        "Blue_Sally_pretty.json": (5, {"HC"}),
        "Charm_Sally_pretty.json": (5, {"BPD"}),
        "Eclair_Sally_pretty.json": (4, set()),
    }

    @pytest.mark.parametrize("fixture_name", sorted(EXPECTED))
    def test_corpus_extraction(self, fixture_name):
        n_bins, abnormal = self.EXPECTED[fixture_name]
        bins = observer.extract_from_file(DATA_DIR / fixture_name)
        assert len(bins) == n_bins
        got = {b.description.split(":")[0].strip() for b in bins if not b.normal}
        assert got == abnormal


class TestObserverGestationalAge:
    def _fetus(self, ega):
        return {
            "fetus": {"fetus_number": 1},
            "measurements": [
                {
                    "label": "HC",
                    "value": 17.5,
                    "unit_of_measure": "cm",
                    "calculated_percentile": 50.0,
                    "calculated_ega": ega,
                }
            ],
        }

    def test_impossible_ega_keeps_the_measurement_without_a_ga(self, caplog):
        term_bins = observer.extract({"fetuses": [self._fetus(500.0)]})

        assert len(term_bins) == 1
        assert term_bins[0].gestational_age_weeks is None
        assert "gestational age" in caplog.text.lower()

    def test_valid_ega_is_kept_as_fractional_weeks(self):
        term_bins = observer.extract({"fetuses": [self._fetus(21.5)]})

        assert term_bins[0].gestational_age_weeks == pytest.approx(21 + 3 / 7)

    def test_apple_sally_ages_come_from_calculated_ega(self):
        bins = observer.extract_from_file(DATA_DIR / "Apple_Sally_pretty.json")

        by_name = {b.description.split(":")[0].strip(): b for b in bins}
        # Observer's calculated_ega is decimal weeks; the TermBin keeps it as
        # completed weeks plus whole days (26.9 -> 26w 6d).
        assert by_name["AC"].gestational_age_weeks == pytest.approx(26 + 6 / 7)
        assert by_name["Femur"].gestational_age_weeks == pytest.approx(27)
        assert all(b.gestational_age_weeks is not None for b in bins)
