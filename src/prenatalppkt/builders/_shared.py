"""Shared helpers for the Observer and ViewPoint Phenopacket builders.

These two builders both build one Phenopacket per fetus from a term-bin
list plus narrative HPO terms, so the GA-resolution, feature-construction,
dedup, and id-formatting logic is identical between them. The gyn builder
has no fetus concept and only reuses `hpo_resource` from here; its own
narrative/id helpers stay local to gyn_phenopacket.py.
"""

from __future__ import annotations

import re
from typing import Optional

import phenopackets.schema.v2 as pps2

from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.hpo import HpoParser
from prenatalppkt.measurements.term_bin import TermBin

_GA_PATTERN = re.compile(r"at (\d+)w(\d+)d")
_DEFAULT_GA = GestationalAge(weeks=27, days=0)


def parse_ga_from_description(description: str) -> Optional[tuple[int, int]]:
    m = _GA_PATTERN.search(description or "")
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def resolve_subject_ga(dating: dict, term_bins: list[TermBin]) -> GestationalAge:
    # TODO @VarenyaJ: dating.get("ga_weeks") is dead code today - neither
    # source's pregnancy-dating parser returns a "ga_weeks" key (both
    # return ga_by_lmp/ga_by_ultrasound/assigned_ga), so this branch never
    # fires and GA always falls through to the description-parsing loop
    # below (or the 27w0d default).
    ga_weeks = dating.get("ga_weeks")
    if ga_weeks:
        return GestationalAge.from_weeks(float(ga_weeks))
    for tb in term_bins:
        parsed = parse_ga_from_description(tb.description)
        if parsed is not None:
            w, d = parsed
            return GestationalAge(weeks=w, days=d)
    return _DEFAULT_GA


def biometry_feature(tb: TermBin) -> pps2.PhenotypicFeature:
    # Known limitation: the onset comes from the age written in the term-bin
    # description, which is the age that this one measurement implies, not the
    # gestational age of the exam. Findings from one exam can therefore get
    # different onsets, and a description without an age falls back to the
    # default. The onset should be the exam's gestational age. See
    # docs/known-limitations.md.
    parsed = parse_ga_from_description(tb.description)
    if parsed is not None:
        w, d = parsed
    else:
        w, d = _DEFAULT_GA.weeks, _DEFAULT_GA.days
    return pps2.PhenotypicFeature(
        type=pps2.OntologyClass(id=tb.hpo_id, label=tb.hpo_label),
        excluded=tb.normal,
        description=f"Biometry: {tb.description}",
        onset=pps2.TimeElement(gestational_age=pps2.GestationalAge(weeks=w, days=d)),
    )


def narrative_feature(
    term, description_prefix: str, subject_ga: GestationalAge
) -> pps2.PhenotypicFeature:
    return pps2.PhenotypicFeature(
        type=pps2.OntologyClass(id=term.hpo_id, label=term.hpo_label),
        excluded=term.excluded,
        description=description_prefix,
        onset=pps2.TimeElement(
            gestational_age=pps2.GestationalAge(
                weeks=subject_ga.weeks, days=subject_ga.days
            )
        ),
    )


def dedup_by_hpo_id(
    features: list[pps2.PhenotypicFeature],
) -> list[pps2.PhenotypicFeature]:
    # Known limitation: this keeps the first feature for each HPO ID and drops
    # the rest. When two measurements map to the same term (for example normal
    # head circumference and normal biparietal diameter), the second
    # measurement and its description are lost from the output. See
    # docs/known-limitations.md.
    seen: set[str] = set()
    out: list[pps2.PhenotypicFeature] = []
    for pf in features:
        if pf.type.id in seen:
            continue
        seen.add(pf.type.id)
        out.append(pf)
    return out


def hpo_resource(hpo_parser: HpoParser) -> pps2.Resource:
    return pps2.Resource(
        id="hp",
        name="human phenotype ontology",
        url="http://purl.obolibrary.org/obo/hp.owl",
        version=hpo_parser.get_version() or "unknown",
        namespace_prefix="HP",
        iri_prefix="http://purl.obolibrary.org/obo/HP_",
    )


def phenopacket_id(accession_id: Optional[str], fetus_number: int) -> str:
    if accession_id:
        return f"{accession_id.lower().replace('_', '-')}-fetus-{fetus_number}"
    return f"fetus-{fetus_number}"


def subject_id(accession_id: Optional[str], fetus_number: int) -> str:
    # TODO(@VarenyaJ): this accession-segment split is reverse-engineered
    # from Columbia/CUIMC Observer exports only (confirmed via Derek's
    # email). We have no real Observer samples from Broad, Charite, or
    # UNSW - confirm this shape holds there before trusting subject.id
    # grouping on non-CUIMC data.
    if accession_id:
        parts = accession_id.lower().replace("_", "-").split("-")
        patient = parts[0]
        if len(parts) > 2:
            return f"{patient}-preg{parts[2]}-fetus-{fetus_number}"
        return f"{patient}-fetus-{fetus_number}"
    return f"fetus-{fetus_number}"
