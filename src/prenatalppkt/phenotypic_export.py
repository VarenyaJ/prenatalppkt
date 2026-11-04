"""
High-level orchestrator for phenotypic exports.
"""

from pathlib import Path
from typing import Optional, Dict, Set, List, Any, Tuple, ClassVar
import logging
import json

import yaml

from prenatalppkt.biometry_reference import FetalGrowthPercentiles
from prenatalppkt.biometry_type import BiometryType
from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.measurement_eval import DEFAULT_MAPPINGS_FILE, MeasurementEvaluation
from prenatalppkt.measurements.percentile_range import PercentileRange
from prenatalppkt.measurements.term_bin import TermBin
from prenatalppkt.term_observation import TermObservation

logger = logging.getLogger(__name__)


class PhenotypicExporter:
    """High-level orchestrator for phenotypic exports."""

    # Lookup table for range to bin_key conversion
    _RANGE_TO_BIN: ClassVar[Dict[Tuple[int, int], str]] = {
        (0, 3): "below_3p",
        (3, 5): "between_3p_5p",
        (5, 10): "between_5p_10p",
        (10, 50): "between_10p_50p",
        (50, 90): "between_50p_90p",
        (90, 95): "between_90p_95p",
        (95, 97): "between_95p_97p",
        (97, 100): "above_97p",
    }

    def __init__(
        self, source: str = "intergrowth", mappings_path: Optional[Path] = None
    ) -> None:
        """
        Initialize exporter.

        Args:
            source: Reference source ("intergrowth" or "nichd")
            mappings_path: Path to YAML mappings (optional)
        """
        self.source = source
        self.reference = FetalGrowthPercentiles(source=source)
        self.evaluator = MeasurementEvaluation(mappings_path=mappings_path)

        self._mappings_path = mappings_path or DEFAULT_MAPPINGS_FILE

        logger.info("Initialized PhenotypicExporter with %s reference", source)

    @property
    def mappings(self) -> Dict[str, Any]:
        """
        Compatibility property for tests.

        Returns dict of measurement types mapped to their available bins.
        """
        with open(self._mappings_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        return self._convert_mappings_format(raw)

    def _convert_mappings_format(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convert new YAML format to old format for backward compatibility."""
        result: Dict[str, Any] = {}

        for meas_type, entry in raw.items():
            range_list = entry["bins"] if isinstance(entry, dict) else entry
            result[meas_type] = {
                "bins": {},
                "normal_bins": [],
                "abnormal_term": {"id": "HP:0000240", "label": "Abnormality"},
            }

            for range_dict in range_list:
                min_p = int(range_dict["min"])
                max_p = int(range_dict["max"])
                range_key = (min_p, max_p)

                bin_key = self._RANGE_TO_BIN.get(range_key)
                if bin_key:
                    result[meas_type]["bins"][bin_key] = {
                        "id": range_dict["id"],
                        "label": range_dict["label"],
                    }

                    if range_dict["normal"]:
                        result[meas_type]["normal_bins"].append(bin_key)

        return result

    def evaluate_to_observation(
        self,
        measurement_type: BiometryType,
        value_mm: float,
        gestational_age_weeks: float,
        normal_bins: Optional[Set[str]] = None,
    ) -> TermObservation:
        """
        Evaluate measurement and return TermObservation.

        Args:
            measurement_type: Type of measurement
            value_mm: Measurement value in millimeters
            gestational_age_weeks: GA as float (e.g., 20.3)
            normal_bins: Optional override for normal ranges (legacy support)

        Returns:
            TermObservation with HPO term
        """
        ga = GestationalAge.from_weeks(gestational_age_weeks)
        measurement_key = measurement_type.value

        percentile = self.reference.lookup_percentile(
            measurement_type=measurement_type,
            gestational_age_weeks=gestational_age_weeks,
            value_mm=value_mm,
        )

        mapper = self.evaluator.get_measurement_mapper(measurement_key)
        if mapper is None:
            raise ValueError(f"No mapper found for {measurement_key}")

        term_obs = mapper.from_percentile(
            percentile, ga
        )  # now uses contains() via TermBin
        return term_obs

    def evaluate_and_export(
        self,
        measurement_type: BiometryType,
        measurement_result: PercentileRange,
        gestational_age: GestationalAge,
        normal_bins: Optional[Set[str]] = None,
    ) -> Dict[str, object]:
        """
        Legacy method for backward compatibility.

        Converts MeasurementResult -> percentile -> TermObservation.

        Args:
            measurement_type: Type of measurement
            measurement_result: Result from ReferenceRange.evaluate()
            gestational_age: Gestational age
            normal_bins: Optional override for normal ranges

        Returns:
            Phenotypic feature dict
        """
        bin_to_percentile: Dict[str, float] = {
            "below_3p": 1.5,
            "between_3p_5p": 4.0,
            "between_5p_10p": 7.5,
            "between_10p_50p": 30.0,
            "between_50p_90p": 70.0,
            "between_90p_95p": 92.5,
            "between_95p_97p": 96.0,
            "above_97p": 98.5,
        }

        percentile = bin_to_percentile.get(measurement_result.bin_key, 50.0)
        measurement_key = measurement_type.value
        mapper = self.evaluator.get_measurement_mapper(measurement_key)

        if mapper is None:
            raise ValueError(f"No mapper found for {measurement_key}")

        term_obs = mapper.from_percentile(percentile, gestational_age)
        return term_obs.to_phenotypic_feature()

    def export_feature(
        self,
        measurement_type: BiometryType,
        measurement_result: PercentileRange,
        gestational_age: GestationalAge,
        normal_bins: Optional[Set[str]] = None,
    ) -> Dict[str, object]:
        """Alias for evaluate_and_export for compatibility."""
        return self.evaluate_and_export(
            measurement_type, measurement_result, gestational_age, normal_bins
        )

    def batch_export(
        self, measurements: List[Tuple[BiometryType, float, float]]
    ) -> List[TermObservation]:
        """
        Export multiple measurements.

        Args:
            measurements: List of (measurement_type, value_mm, ga_weeks) tuples

        Returns:
            List of TermObservations
        """
        results: List[TermObservation] = []
        errors: List[Tuple[BiometryType, str]] = []

        for meas_type, value, ga_weeks in measurements:
            try:
                term_obs = self.evaluate_to_observation(
                    measurement_type=meas_type,
                    value_mm=value,
                    gestational_age_weeks=ga_weeks,
                )
                results.append(term_obs)
            except (ValueError, KeyError) as e:  # noqa: PERF203  # Batch processing requires per-item error handling
                logger.error("Error processing %s: %s", meas_type, e)
                errors.append((meas_type, str(e)))

        if errors:
            logger.warning("Encountered %d errors during batch export", len(errors))

        return results

    def to_json(
        self,
        term_observations: List[TermObservation],
        pretty: bool = False,
        term_bins: Optional[List[TermBin]] = None,
    ) -> str:
        """
        Convert TermObservations to Phenopacket JSON string.

        Args:
            term_observations: List of TermObservation objects
            pretty: Whether to pretty-print the JSON
            term_bins: Optional list of TermBins carrying LOINC + raw values;
                when supplied, a `measurements` array is added alongside
                `phenotypicFeatures` (bins without LOINC/value are skipped).

        Returns:
            JSON string
        """
        features = [obs.to_phenotypic_feature() for obs in term_observations]

        phenopacket: Dict[str, Any] = {
            "phenotypicFeatures": features,
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "prenatalppkt",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "version": "2024-08-13",
                    }
                ],
            },
        }

        if term_bins:
            measurements = [
                msmt
                for tb in term_bins
                if (msmt := tb.to_measurement_dict()) is not None
            ]
            if measurements:
                phenopacket["measurements"] = measurements

        if pretty:
            return json.dumps(phenopacket, indent=2)
        return json.dumps(phenopacket)
