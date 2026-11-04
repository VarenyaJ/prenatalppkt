"""
Loads the measurement registry: one entry per biometry measurement, with its
role, its biometry-mappings key and the label each export format uses.
Labels confirmed in a real export are kept apart from guessed ones, but both
are used for lookups.

The per-format name maps, required/optional lists and YAML-key lookup are all
built from this registry. It deliberately works with plain strings (the
standard measurement names) so the modules that build those tables can import
it without an import cycle.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

import yaml

from prenatalppkt.data_files import MAPPINGS_DIR

ROLES: FrozenSet[str] = frozenset({"required", "optional", "t1"})
SOURCES: Tuple[str, ...] = ("observer", "viewpoint_text", "viewpoint_hl7", "generic")
_FIELDS: FrozenSet[str] = frozenset(
    {"role", "yaml_key", "unmapped_reason", "aliases", "guessed_aliases"}
)

DEFAULT_REGISTRY_PATH = MAPPINGS_DIR / "measurement_registry.yaml"


@dataclass(frozen=True)
class MeasurementSpec:
    """One measurement's registry entry, checked at load time."""

    name: str
    role: str
    yaml_key: Optional[str]
    unmapped_reason: Optional[str]
    aliases: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    guessed_aliases: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)

    def all_aliases(self, source: str) -> Tuple[str, ...]:
        """Confirmed then guessed labels for one source."""
        return self.aliases[source] + self.guessed_aliases[source]


def _parse_aliases(name: str, key: str, entry: dict) -> Dict[str, Tuple[str, ...]]:
    raw_aliases = entry.get(key) or {}
    if not isinstance(raw_aliases, dict):
        raise ValueError(f"{name}: {key} must be a mapping")
    unknown_sources = set(raw_aliases) - set(SOURCES)
    if unknown_sources:
        raise ValueError(f"{name}: unknown sources in {key}: {sorted(unknown_sources)}")
    return {
        source: tuple(str(label) for label in raw_aliases.get(source) or ())
        for source in SOURCES
    }


def _parse_entry(name: str, entry: object) -> MeasurementSpec:
    if not isinstance(entry, dict):
        raise ValueError(f"{name}: entry must be a mapping")
    unknown = set(entry) - _FIELDS
    if unknown:
        raise ValueError(f"{name}: unknown fields {sorted(unknown)}")

    role = entry.get("role")
    if role not in ROLES:
        raise ValueError(f"{name}: role must be one of {sorted(ROLES)}, got {role!r}")

    yaml_key = entry.get("yaml_key")
    unmapped_reason = entry.get("unmapped_reason")
    if (yaml_key is None) == (unmapped_reason is None):
        raise ValueError(f"{name}: needs exactly one of yaml_key or unmapped_reason")

    aliases = _parse_aliases(name, "aliases", entry)
    guessed = _parse_aliases(name, "guessed_aliases", entry)
    for source in SOURCES:
        labels = aliases[source] + guessed[source]
        if len(set(labels)) != len(labels):
            raise ValueError(f"{name}: duplicate {source} alias")

    return MeasurementSpec(
        name=name,
        role=role,
        yaml_key=yaml_key,
        unmapped_reason=unmapped_reason,
        aliases=aliases,
        guessed_aliases=guessed,
    )


def load_registry(path: Optional[Path] = None) -> Dict[str, MeasurementSpec]:
    """
    Load and check the measurement registry.

    Args:
        path: Registry YAML; defaults to the bundled measurement_registry.yaml

    Returns:
        Measurement specs keyed by standard measurement name, in file order

    Raises:
        ValueError: If an entry is malformed, or the same alias (confirmed or
            guessed) appears under two measurements for one source
    """
    with open(path or DEFAULT_REGISTRY_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    specs = {str(name): _parse_entry(str(name), entry) for name, entry in raw.items()}

    for source in SOURCES:
        owner: Dict[str, str] = {}
        for spec in specs.values():
            for label in spec.all_aliases(source):
                if label in owner:
                    raise ValueError(
                        f"{source} alias {label!r} used by both {owner[label]} and {spec.name}"
                    )
                owner[label] = spec.name

    return specs


REGISTRY: Dict[str, MeasurementSpec] = load_registry()
