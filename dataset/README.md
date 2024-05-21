# Benchmark Dataset

## Precursor mixture dataset

This dataset contains XRD patterns (.xrdml files) for 50 different precursor mixtures.
Each precursor mixture is an equal weight combination of three or four different precursors. For
each mixture, two XRD scan is performed at different resolution (`2-min` fast scan and
`12-min` normal scan).

Each file has the following format:

```
precursor1_precursor2_precursor3[_precursor4].xrd_scan_type.xrdml
```

## Binary reaction dataset

This dataset contains XRD patterns (.xrdml files) for powder samples obtained from 20
binary (i.e., two precursor) reactions performed in the A-Lab. Each scan was performed
as 8-minute scans on the Malvern Panalytical AERIS X-ray diffractometer. The reactions
are all equi-cation, except for reactions with NH4H2PO4, which are equimolar.

Each file has the following format:

```
Xprecursor1-Yprecursor2_ZZZC_60min.xrdml
```

Where X and Y are the stoichiometric coefficients of the precursors, and ZZZ is the
temperature of the annealing hold time (60 mins) for all reactions.
