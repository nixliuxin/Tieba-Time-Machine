"""
par2_protect.py - Generate PAR2 parity/recovery files for tar archives.

Usage:
    python par2_protect.py --dir ./archives/forum_name --redundancy 5

Requires:
    par2cmdline-turbo (https://github.com/animetosho/par2cmdline-turbo)
    Windows: download par2.exe and place in PATH, or pass --par2-bin path
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys


def find_par2_binary(custom_path: str = None) -> str:
    """Locate the par2 executable."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    found = shutil.which("par2") or shutil.which("par2.exe") or shutil.which("par2j64")
    if found:
        return found

    return None


def create_par2(par2_bin: str, target_file: str, redundancy: int = 5):
    """Create PAR2 recovery files for the target."""
    par2_base = target_file + ".par2"
    if os.path.exists(par2_base):
        print(f"  Already exists: {par2_base}")
        return True

    print(f"  Creating PAR2 ({redundancy}% redundancy): {os.path.basename(target_file)}")
    cmd = [
        par2_bin, "create",
        f"-r{redundancy}",
        "-n1",
        target_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            par2_files = glob.glob(target_file + "*.par2")
            total_size = sum(os.path.getsize(f) for f in par2_files)
            print(f"    OK! PAR2 size: {total_size / 1024 / 1024:.1f} MB")
            return True
        else:
            print(f"    Failed: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("    Timed out!")
        return False


def verify_par2(par2_bin: str, par2_file: str) -> bool:
    """Verify PAR2 integrity."""
    print(f"  Verifying: {os.path.basename(par2_file)}")
    cmd = [par2_bin, "verify", par2_file]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print("    Passed!")
            return True
        else:
            print(f"    Failed: {result.stdout[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print("    Verification timed out!")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate PAR2 parity files for tar archives")
    parser.add_argument("--dir", required=True, help="Directory containing tar files")
    parser.add_argument("--redundancy", type=int, default=5, help="Redundancy percentage (default: 5)")
    parser.add_argument("--par2-bin", default=None, help="Path to par2 executable")
    parser.add_argument("--verify", action="store_true", help="Verify existing PAR2 files only")
    args = parser.parse_args()

    par2_bin = find_par2_binary(args.par2_bin)
    if not par2_bin:
        print("Error: par2 executable not found!")
        print("Install par2cmdline-turbo: https://github.com/animetosho/par2cmdline-turbo")
        print("Or specify path with --par2-bin")
        sys.exit(1)

    print(f"Using par2: {par2_bin}")

    tar_files = glob.glob(os.path.join(args.dir, "*.tar"))
    if not tar_files:
        print(f"No .tar files found in {args.dir}")
        sys.exit(0)

    print(f"Found {len(tar_files)} tar file(s)")

    if args.verify:
        for tar_file in tar_files:
            par2_file = tar_file + ".par2"
            if os.path.exists(par2_file):
                verify_par2(par2_bin, par2_file)
            else:
                print(f"  Skipped (no PAR2): {os.path.basename(tar_file)}")
    else:
        for tar_file in tar_files:
            create_par2(par2_bin, tar_file, args.redundancy)

    print("\nDone!")


if __name__ == "__main__":
    main()
