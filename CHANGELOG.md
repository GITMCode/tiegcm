# Changes made in MILE branch

Care was taken to not alter tiegcm functionality AT ALL. With Electrodynamics, Weimer
potentials are <3% different.

## Summary of changes

### Configuration usability changes:

- `tiegcmrun.py` now has an entrypoint at the root of the repository. The file is
  functionally empty and all logic remains in `scripts/tiegcmrun.py`.
- Unite global variables (and refactor) so `tiegcmrun.py --help` does not error
  when variables are not yet set or python libraries are missing.
- Add several (previously) created directories (and `tiegcmdata/`) to .gitignore

### Configuration functional changes

- Remove Pleiades Makefile stubs since the machine has been decommissioned
- Add automatic HPC-system detection to `tiegcmrun.py`
  - Currently only detects Aitken and Derecho
  - Add notes to bundled Makefile stubs about `ESMF.mk` being sourced from another
    user's directory

### New configure script `config.py`

> Background:
>
> - Interactive wizard needed to be run to change compilers or resolution.
> - Wizard would need to be re-run if I forgot to add `-c` (not compiled by default)
> - Could not re-compile from root of repository

- Script ***only*** sets vertical/horizontal resolution & compiler. User must run
  `make`, `make rundir`, and set the dates/paths in `tiegcm.inp`.
- Template `tiegcm.inp` for flexibility. Few env-vars required
- Auto detects (or accepts arguments for) system compiler. Detection order is
  `$FC` (env var) > `ifort` (intel) > `gfortran` (gnu).
- Proactively use $ESMFMKFILE env var (set upon loading module or installing) to
  determine compiler arguments.
- Adds and uses generic intel/gfortran (linux) Makefile stubs. Both are tested.
- Run without arguments to print current configuration settings
- Creates one common executable in `build/`. Additional run directories
  `make rundir RUN='/path/to/or/name_of_run'` symlink to this common executable.
  - Most HPC systems do not recommend storing executables on `$SCRATCH`
  - Changed settings in the code now will be reflected in *each* run directory
    automatically
  - Automatically symlinks `tiegcmdata/` if it is in `$PWD` or set as env-var.
- Auto-clones Electrodynamics & srcIndices if `--mile`

### Electrodynamics changes

- `config.py` has a `--mile` flag which will automatically clone Electrodynamics/, a
  Fortran-based IE library with many empirical models.
- `auroral_model` option added. Default `emery` option to not affect current
  functionality.
- `Makefile.conf` and `Makefile.dirs` created with Electrodynamics-specific compilation
  directives
- All electrodynamics-related code is blocked with fpp directives, meaning they are not
  seen unless user explicitly opts in.
- Machinery to pass names/times/indices to electrodynamics, and to get values from
  electrodynamics.

## The implementation

- Heelis, Emery, Weimer left in place and not ported to electrodynamics.
- Cusp, drizzle, SAPS, extra precipitation are all usable with FTA/FRE/etc.
- TIEGCM version of Weimer is still run if model = Weimer05. Emery is run regardless.
  The values are overwritten before being consumed (but consumed & output correctly).
  - Tracing through the code:
    - Outputs from the Emery auroral model depend on which potential model was used.
      Each dt, the auroral boundary is written globally from ctpoten (derived from Kp if
      Weimer is not used) & HP, then eFlux & alfa (avgE) are calculated. Then the
      potentials run, Heelis consumes the boundary, Weimer overwrites the auroral
      boundary values (to be read by aurora_cons the following dt).
    - Heelis does not calculate `ctpoten` (the cross-polar-cap-potential). This is
      calculated from Kp (if Weimer is not used) before Emery runs.
    - In other words, Emery depends on, or is a dependent of, both Heelis ***and***
      Weimer. Heelis depends on Emery. Things change with Gamera coupling and AMIE files
      (slightly). But the dependency is too inter-twined for either Heelis or Emery to
      be removed. Weimer05 boundary calculation is non-standard and the licencing will
      not permit it be moved to Electrodynamics.
  - Many downstream functions require `wei05sc_loc` was called when Weimer is the
    potential model. Electrodynamics does not support transferring the entire return
    values of `wei05sc_loc`
- If `auroral_model` is *not* Emery, all aurora code is still executed. Cusp, drizzle,
  saps all rely on values set by Weimer or `aurora_cons`
  - NEW: Add optio to toggle cusp, drizzle, low-energy -e to input.F


## Validation

- Non-electrodynamics runs are bit-identical
- TIEGCM vs Electrodynamics Weimer `POTEN` have extrema <3% and average <1-2% difference

## Other changes (all minor)

- Add aurora model name to outputs
- Add total integrated hemispheric power to outputs ('regular aurora' + cusp + drizzle +
  soft (high-alt) electrons). Does not include solar protons & high-energy electrons.
- Bug: exit before doing MPI stuff. Calling executable without MPI would permanently
  hang terminal (no Ctrl + C/D/Z/etc.).

## Known remaining issues:

- No Electrodynamics AMIE. Probably fine. Only diffuse electron precipitation is
  supported from Ovation. TIEGCM assumes all auroral precipitation are electrons with a
  maxwellian distribution, so monoenergetic/wave/ion precipitation are not implemented.
