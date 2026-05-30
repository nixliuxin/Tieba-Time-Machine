"""
run_all.py - Run the full consolidation pipeline in one shot.

Usage:
    python run_all.py --source ./scraped_data --output ./archives

Steps:
  1. Merge content.db + json -> per-forum master.db
  2. Pack media -> per-forum .tar + media_index.json
  3. Generate PAR2 parity files (if par2 is available)
"""

import argparse
import os
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(description: str, script: str, args: list):
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")

    cmd = [sys.executable, os.path.join(TOOLS_DIR, script)] + args
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n[ERROR] {description} failed (exit code {result.returncode})")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the full Tieba archive consolidation pipeline")
    parser.add_argument("--source", required=True, help="Source data directory (raw scraped data)")
    parser.add_argument("--output", required=True, help="Output directory for consolidated archives")
    parser.add_argument("--skip-media", action="store_true", help="Skip media packing step")
    parser.add_argument("--skip-par2", action="store_true", help="Skip PAR2 generation step")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if not run_step(
        "Step 1/3: Merge databases and metadata -> per-forum master.db",
        "merge_archive.py",
        ["--source", args.source, "--output", args.output],
    ):
        sys.exit(1)

    if not args.skip_media:
        if not run_step(
            "Step 2/3: Pack media files -> tar",
            "pack_media.py",
            ["--source", args.source, "--output", args.output],
        ):
            print("[WARN] Media packing failed, continuing...")

    if not args.skip_par2:
        for name in os.listdir(args.output):
            sub = os.path.join(args.output, name)
            if os.path.isdir(sub) and any(f.endswith(".tar") for f in os.listdir(sub)):
                run_step(
                    f"Step 3/3: PAR2 parity - {name}",
                    "par2_protect.py",
                    ["--dir", sub],
                )

    print(f"\n{'='*60}")
    print("  All done!")
    print(f"{'='*60}")
    print(f"\nOutput directory: {args.output}")
    print("Files:")
    for name in sorted(os.listdir(args.output)):
        sub = os.path.join(args.output, name)
        if os.path.isdir(sub):
            print(f"  {name}/")
            for f in sorted(os.listdir(sub)):
                full = os.path.join(sub, f)
                if os.path.isfile(full):
                    size_mb = os.path.getsize(full) / 1024 / 1024
                    print(f"    {f}  ({size_mb:.1f} MB)")

    server_dir = os.path.join(TOOLS_DIR, "..", "server")
    print(f"\nTo start the reader:")
    print(f"  cd {server_dir}")
    print(f"  set TIEBA_DATA_DIR={args.output}")
    print(f"  uvicorn main:app --port 8900")


if __name__ == "__main__":
    main()
