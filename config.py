#!/usr/bin/env python3
"""
config.py  —  Configure a TIE-GCM build.

Writes build/Make.env and build/defs.h, copies build infrastructure from
scripts/, and generates a root-level Makefile.  Build with  make.

Usage:
    python config.py --horires DEG [options]   # configure
    python config.py                           # show current configuration
    python config.py --uninstall               # remove all generated files

Compiler is auto-detected if --compiler is omitted:
    $FC  →  ifort (if found)  →  gfortran
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

_TIEGCMHOME = os.path.dirname(os.path.abspath(__file__))

_RES_TABLE = {
    5.0:   {"vertres": 0.5,    "nres_grid": 5, "step": 60},
    2.5:   {"vertres": 0.25,   "nres_grid": 5, "step": 30},
    1.25:  {"vertres": 0.125,  "nres_grid": 6, "step": 10},
    0.625: {"vertres": 0.0625, "nres_grid": 7, "step": 5},
}

_COMPILER_MAKEFILE = {
    "intel":    "Make.intel_linux",
    "ifort":    "Make.intel_linux",
    "gnu":      "Make.gfort_linux",
    "gfortran": "Make.gfort_linux",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_compiler(arg):
    """Return compiler key: CLI arg > $FC > ifort-probe > gfortran."""
    if arg:
        key = arg.strip().lower()
        if key not in _COMPILER_MAKEFILE:
            sys.exit(
                f"Error: unsupported compiler {arg!r}. "
                f"Choose from: {', '.join(sorted(set(_COMPILER_MAKEFILE)))}"
            )
        return key

    fc = os.environ.get("FC", "").strip().lower().split('/')[-1]
    if fc:
        if fc not in _COMPILER_MAKEFILE:
            sys.exit(
                f"Error: $FC={fc!r} is not a recognised compiler. "
                f"Choose from: {', '.join(sorted(set(_COMPILER_MAKEFILE)))}"
            )
        return fc

    for candidate in ("ifort", "gfortran"):
        try:
            subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    sys.exit(
        "Error: no compiler found. Install ifort or gfortran, "
        "or set $FC / use --compiler."
    )


def _resolve_tiegcmdata(arg):
    if arg:
        p = os.path.realpath(os.path.expanduser(arg))
        if not os.path.isdir(p):
            sys.exit(f"Error: TIEGCMDATA path does not exist: {p}")
        return p
    env = os.environ.get("TIEGCMDATA", "").strip()
    if env and os.path.isdir(env):
        return os.path.realpath(env)
    candidate = os.path.join(_TIEGCMHOME, "tiegcmdata")
    if os.path.isdir(candidate):
        return os.path.realpath(candidate)
    sys.exit(
        "Error: TIEGCMDATA not set and no tiegcmdata/ directory found.\n"
        "       Set $TIEGCMDATA or pass --tiegcmdata <dir>."
    )


def _read_make_env(builddir):
    """Parse build/Make.env into a key→value dict."""
    result = {}
    path = os.path.join(builddir, "Make.env")
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _read_defs_h(builddir):
    """Parse build/defs.h into a key→value dict."""
    result = {}
    with open(os.path.join(builddir, "defs.h")) as f:
        for line in f:
            m = re.match(r"#define\s+(\w+)\s+([\S]+)", line)
            if m:
                result[m.group(1)] = m.group(2)
    return result


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def _write_defs_h(builddir, horires, vertres, zitop, nres_grid):
    content = (
        f"#define DLAT {horires}\n"
        f"#define DLON {horires}\n"
        f"#define GLON1 -180\n"
        f"#define DLEV {vertres}\n"
        f"#define ZIBOT -7\n"
        f"#define ZITOP {zitop}\n"
        f"#define NRES_GRID {nres_grid}\n"
    )
    path = os.path.join(builddir, "defs.h")
    changed = True
    if os.path.isfile(path):
        with open(path) as f:
            changed = f.read() != content
    with open(path, "w") as f:
        f.write(content)
    return changed


def _write_make_env(builddir, make_fragment, srcdir, exe_path,
                    coupling=False, hidra=False, debug=False, havemile=False,
                    tiegcmhome=""):
    content = (
        f"MAKE_MACHINE  = {make_fragment}\n"
        f"DIRS          = . {srcdir}\n"
        f"EXECNAME      = {exe_path}\n"
        f"NAMELIST      = \n"
        f"OUTPUT        = \n"
        f"COUPLING      = {str(coupling).upper()}\n"
        f"HIDRA         = {str(hidra).upper()}\n"
        f"DEBUG         = {str(debug).upper()}\n"
        f"HAVEMILE      = {str(havemile).upper()}\n"
        f"IEDIR         = {tiegcmhome}/ext/Electrodynamics\n"
    )
    with open(os.path.join(builddir, "Make.env"), "w") as f:
        f.write(content)


def _write_root_makefile(tiegcmhome, tiegcmdata, gswm_res):
    template_path = os.path.join(tiegcmhome, "scripts", "Makefile.tmpl")
    with open(template_path, "r") as f:
        template = f.read()

    content = template.format(
        tiegcmhome=tiegcmhome,
        tiegcmdata=tiegcmdata,
        gswm_res=gswm_res
    )

    with open(os.path.join(tiegcmhome, "Makefile"), "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _configure_mile(havemile, tiegcmhome, utildir):
    if not havemile:
        return

    ext_dir = os.path.join(tiegcmhome, "ext", "Electrodynamics")
    repo_url = "https://github.com/GITMCode/Electrodynamics.git"
    if not os.path.isdir(ext_dir):
        print("  Cloning Electrodynamics into ext/Electrodynamics (with HTTPS)...")
        result = subprocess.run(["git", "clone", repo_url, ext_dir],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print("  Electrodynamics clone failed. Perhaps try cloning it manually?")
            print(f"        {result.stderr.strip()}")
    else:
        print("  MILE: ext/Electrodynamics found — pulling latest...")
        result = subprocess.run(["git", "-C", ext_dir, "pull"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print("  Warning: git pull of 'ext/Electrodynamics' failed, continuing.")
            print(f"        {result.stderr.strip()}")

    for fname in ["Makefile.dirs", "Makefile.conf"]:
        src = os.path.join(utildir, fname)
        dest = os.path.join(tiegcmhome, fname)
        if os.path.isfile(src):
            shutil.copy(src, dest)

    local_path = os.path.join(ext_dir, "build", "Makefile.local")
    with open(local_path, "w") as f:
        f.write(f"DIRSFILE := {tiegcmhome}/Makefile.dirs\n")
        f.write(f"BUILDDIR  := {tiegcmhome}\n")

    depend_path = os.path.join(ext_dir, "src", "Makefile.DEPEND")
    open(depend_path, "a").close()

def configure(args):
    compiler   = _detect_compiler(getattr(args, "compiler", None))
    horires    = float(args.horires)
    zitop      = float(args.zitop)
    debug      = bool(args.debug)
    coupling   = bool(args.coupling)
    hidra      = bool(args.hidra)
    havemile   = bool(args.havemile)
    tiegcmdata = _resolve_tiegcmdata(getattr(args, "tiegcmdata", None))

    if horires not in _RES_TABLE:
        sys.exit(
            f"Error: unsupported horires {horires}. "
            f"Choose from: {', '.join(str(k) for k in _RES_TABLE)}"
        )

    res           = _RES_TABLE[horires]
    make_fragment = _COMPILER_MAKEFILE[compiler]
    builddir      = os.path.join(_TIEGCMHOME, "build")
    srcdir        = os.path.join(_TIEGCMHOME, "src")
    utildir       = os.path.join(_TIEGCMHOME, "scripts")
    exe_path      = os.path.join(builddir, "tiegcm.exe")

    os.makedirs(builddir, exist_ok=True)

    for fname in [make_fragment, "Makefile", "mkdepends"]:
        dest = os.path.join(builddir, fname)
        if not os.path.isfile(dest):
            src = os.path.join(utildir, fname)
            if os.path.isfile(src):
                shutil.copy(src, dest)

    _configure_mile(havemile, _TIEGCMHOME, utildir)

    defs_changed = _write_defs_h(
        builddir, horires, res["vertres"], zitop, res["nres_grid"]
    )
    _write_make_env(
        builddir, make_fragment, srcdir, exe_path, coupling, hidra, debug, havemile,
        _TIEGCMHOME
    )
    gswm_res = f"{horires}d"
    _write_root_makefile(_TIEGCMHOME, tiegcmdata, gswm_res)

    print("Configured TIEGCM:")
    print(f"  Compiler   : {compiler}  ({make_fragment})")
    print(f"  Resolution : {horires} deg horizontal / {res['vertres']} deg vertical")
    print(f"  ZITOP      : {zitop}  (log-pressure level)")
    print(f"  TIEGCMDATA : {tiegcmdata}")
    print(f"  Debug={debug}  Coupling={coupling}  HIDRA={hidra}  HAVEMILE={havemile}")
    if defs_changed:
        print("  >> Resolution changed — run  make clean  before rebuilding.")
    print()
    print("  make       — build tiegcm.exe")
    print("  Run config.py again if you want to change anything.")
    print("  IMPORTANT: run scripts/interpic.py to generate new inputs!")


def show_status():
    """ Helper function to print the current model configuration.

    Prints:
    - compiler (makefile stub used)
    - horizontal / vertical resolution
    - zitop
    - location of executable (built T/F)
    - Flags used to configure
    - some usage tips

    """

    builddir = os.path.join(_TIEGCMHOME, "build")
    env_path = os.path.join(builddir, "Make.env")
    defs_path = os.path.join(builddir, "defs.h")

    if not os.path.isfile(env_path) or not os.path.isfile(defs_path):
        _build_parser().print_help()
        print("\nNot configured. Run:")
        print("\tpython config.py -r/-hr/--horires <deg>  to configure")
        print("\tpython config.py --help                  to see options")
        print("\tpython tiegcmrun.py                      for an interactive configurator")
        return

    env  = _read_make_env(builddir)
    defs = _read_defs_h(builddir)
    exe  = env.get("EXECNAME", "?")

    print("Current TIEGCM configuration:")
    print(f"  Compiler   : {env.get('MAKE_MACHINE', '?')}")
    print(f"  Resolution : {defs.get('DLAT', '?')} deg horizontal / {defs.get('DLEV', '?')} deg vertical")
    print(f"  ZITOP      : {defs.get('ZITOP', '?')}  (log-pressure level)")
    print(f"  Executable : {exe}" + ("  (built)" if os.path.isfile(exe) else "  (not yet built)"))
    print(f"  Debug={env.get('DEBUG','?')}  Coupling={env.get('COUPLING','?')}  HIDRA={env.get('HIDRA','?')}  HAVEMILE={env.get('HAVEMILE','?')}")
    print()
    print("  python config.py -r/-hr/--horires <deg>      — reconfigure")
    print("  python config.py -u / --uninstall     — uninstall")


def uninstall():
    builddir = os.path.join(_TIEGCMHOME, "build")
    utildir  = os.path.join(_TIEGCMHOME, "scripts")

    # Determine which Make.* fragments config.py could have copied
    script_fragments = []
    if os.path.isdir(utildir):
        script_fragments = [
            f for f in os.listdir(utildir) if f.startswith("Make.")
        ]

    targets = (
        [os.path.join(_TIEGCMHOME, "Makefile"), os.path.join(_TIEGCMHOME, "Makefile.dirs"), 
         os.path.join(_TIEGCMHOME, "Makefile.def"), os.path.join(_TIEGCMHOME, "Makefile.conf")]
        + [os.path.join(builddir, f) for f in ["Make.env", "defs.h", "Makefile", "mkdepends"]]
        + [os.path.join(builddir, f) for f in script_fragments]
    )

    removed = []
    for path in targets:
        if os.path.isfile(path):
            os.remove(path)
            removed.append(os.path.relpath(path, _TIEGCMHOME))

    # Remove build/ itself if now empty
    if os.path.isdir(builddir):
        shutil.rmtree(builddir)
        removed.append("build/")

    if removed:
        print("Removed:")
        for f in removed:
            print(f"  {f}")
    else:
        print("Nothing to remove.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(
        description="Configure a TIE-GCM build.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run with no arguments to show the current configuration.\n"
            "Compiler auto-detection order: $FC > ifort > gfortran.\n\n"
            "Examples:\n"
            "  python config.py --horires 2.5\n"
            "  python config.py --horires 2.5 --compiler intel --debug\n"
            "  python config.py --uninstall\n"
            "  python config.py      -> No arguments to see current settings\n"
        ),
    )
    p.add_argument(
        "-hr", "--horires", "-r", default=None, type=float, metavar="DEG",
        help="Horizontal resolution in degrees (5, 2.5, 1.25, 0.625). Required.",
    )
    p.add_argument(
        "--compiler", "-c", default=None,
        help="Compiler: intel/ifort or gnu/gfortran. Default: auto-detected.",
    )
    p.add_argument(
        "--zitop", "-z", default=7.0, type=float, metavar="LEVEL",
        help=("Model top in log-pressure coordinates. Default: 7. "
        "NOTE: Not all files in $ITEGCMDATA/source/ can be used for zitop>7. "
        "Recommend running interpic.py if you change this"),
    )
    p.add_argument("--debug",    "-d", action="store_true", help="Enable debug compilation.")
    p.add_argument("--coupling",       action="store_true", help="Enable GAMERA coupling.")
    p.add_argument("--hidra",          action="store_true", help="Enable HIDRA coupling.")
    p.add_argument("--mile", dest="havemile", action="store_true", help="Enable Electrodynamics (MILE) integration.")
    p.add_argument(
        "--tiegcmdata", default=None, metavar="DIR",
        help="Path to TIEGCMDATA directory. Default: $TIEGCMDATA or tiegcmdata/.",
    )
    p.add_argument(
        "--uninstall", "-u", action="store_true",
        help="Remove all files generated by config.py and exit.",
    )
    return p


def main():
    if len(sys.argv) == 1:
        show_status()
        return

    args = _build_parser().parse_args()

    if args.uninstall:
        uninstall()
        return

    if args.horires is None:
        _build_parser().error("--horires / -r is required")

    configure(args)


if __name__ == "__main__":
    main()
