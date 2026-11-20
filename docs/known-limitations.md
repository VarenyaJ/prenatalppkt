# Known limitations

These are known problems in the current output. Each one has an issue with the plan to fix it. The examples use the synthetic Apple Sally fixture.

## Normal biometry results exclude terms that are too broad

A biometry value in a normal percentile bin is written as an excluded phenotypic feature. An excluded HPO term also excludes all of its descendants, so the term should describe only the size that the measurement checks. Today several normal bins use a term for a whole structure or system:

- a normal femur length excludes HP:0002823 "Abnormal femur morphology", which has 87 descendants in HPO 2026-09-01, including HP:0002980 "Femoral bowing";
- a normal abdominal circumference excludes HP:0034207 "Abnormal fetal gastrointestinal system morphology", which includes HP:0010943 "Echogenic fetal bowel";
- the same pattern affects crown-rump length, tibia, fibula, radius, ulna, foot and humerus lengths, the cerebellum, the nasal bone and the lateral ventricles.

A cohort search for one of those excluded descendants would wrongly count a fetus with a normal measurement as examined and negative. The fix is a size-specific term for each normal bin, or no excluded term, after clinical review. Issue: [#41](https://github.com/VarenyaJ/prenatalppkt/issues/41).

## Findings take their onset from each measurement's own age

The onset of each biometry finding is the gestational age that the single measurement implies, read back from the description text, not the gestational age of the exam. For Apple Sally the exam is at 26w4d, but the findings say 26w6d and later. When no age can be read, the onset falls back to a default. Issue: [#42](https://github.com/VarenyaJ/prenatalppkt/issues/42) (and #14).

## Measurements that map to the same term drop a value

Normal head circumference, biparietal diameter and occipitofrontal diameter map to the same excluded term. Deduplication keeps only the first feature for each term, so the other measurements and their values disappear from the output. Issue: [#43](https://github.com/VarenyaJ/prenatalppkt/issues/43).

## Measurements are not yet written as Measurement records

Values, units and centiles exist only in the feature description text. Writing every value as a Phenopacket Measurement, with the same source text as the feature, keeps the exact numbers. Issue: [#39](https://github.com/VarenyaJ/prenatalppkt/issues/39).

## Other

- The `prenatalppkt` console command is declared but has no module yet: [#44](https://github.com/VarenyaJ/prenatalppkt/issues/44).
- Out-of-date links and counts in the docs, and no tagged release yet: [#45](https://github.com/VarenyaJ/prenatalppkt/issues/45).
