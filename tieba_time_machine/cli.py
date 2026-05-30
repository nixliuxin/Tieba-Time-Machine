"""
Unified CLI entry point for tieba-tools.

Dispatches subcommands to the appropriate scripts via subprocess,
avoiding import-path conflicts with the scraper's sys.path setup.
"""

import argparse
import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPER_DIR = os.path.join(ROOT_DIR, "scraper")
TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
SERVER_DIR = os.path.join(ROOT_DIR, "server")


def cmd_scrape(args):
    """Scrape an entire forum by name."""
    cmd = [
        sys.executable, "-u",
        os.path.join(SCRAPER_DIR, "backup_forum.py"),
        args.forum,
        args.output,
    ]
    if args.concurrency:
        cmd += ["--concurrency", str(args.concurrency)]
    sys.exit(subprocess.run(cmd).returncode)


def cmd_scrape_user(args):
    """Scrape all threads by a specific user."""
    cmd = [
        sys.executable, "-u",
        os.path.join(SCRAPER_DIR, "backup_user.py"),
        args.user,
        args.output,
    ]
    if args.concurrency:
        cmd += ["--concurrency", str(args.concurrency)]
    sys.exit(subprocess.run(cmd).returncode)


def cmd_merge(args):
    """Merge scraped data into per-forum master.db."""
    cmd = [
        sys.executable, "-u",
        os.path.join(TOOLS_DIR, "merge_archive.py"),
        "--source", args.source,
        "--output", args.output,
    ]
    if args.forum:
        cmd += ["--forum", args.forum]
    sys.exit(subprocess.run(cmd).returncode)


def cmd_pack(args):
    """Pack media into per-forum tar archives with index."""
    cmd = [
        sys.executable, "-u",
        os.path.join(TOOLS_DIR, "pack_media.py"),
        "--source", args.source,
        "--output", args.output,
    ]
    if args.forum:
        cmd += ["--forum", args.forum]
    sys.exit(subprocess.run(cmd).returncode)


def cmd_par2(args):
    """Generate PAR2 parity files for tar archives."""
    cmd = [
        sys.executable, "-u",
        os.path.join(TOOLS_DIR, "par2_protect.py"),
        "--dir", args.dir,
    ]
    if args.redundancy:
        cmd += ["--redundancy", str(args.redundancy)]
    sys.exit(subprocess.run(cmd).returncode)


def cmd_pipeline(args):
    """Run the full pipeline: merge -> pack -> par2."""
    cmd = [
        sys.executable, "-u",
        os.path.join(TOOLS_DIR, "run_all.py"),
        "--source", args.source,
        "--output", args.output,
    ]
    if args.skip_media:
        cmd.append("--skip-media")
    if args.skip_par2:
        cmd.append("--skip-par2")
    sys.exit(subprocess.run(cmd).returncode)


def cmd_serve(args):
    """Start the local reader backend."""
    env = os.environ.copy()
    env["TIEBA_DATA_DIR"] = args.data_dir
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    sys.exit(subprocess.run(cmd, cwd=SERVER_DIR, env=env).returncode)


def main():
    parser = argparse.ArgumentParser(
        prog="tieba",
        description="Tieba-Tools: archive Baidu Tieba forums and read them offline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # tieba scrape
    p_scrape = sub.add_parser("scrape", help="Scrape an entire forum")
    p_scrape.add_argument("forum", help="Forum name (without the trailing 'ba')")
    p_scrape.add_argument("-o", "--output", required=True, help="Output directory")
    p_scrape.add_argument("-c", "--concurrency", type=int, help="Max concurrent downloads")
    p_scrape.set_defaults(func=cmd_scrape)

    # tieba scrape-user
    p_user = sub.add_parser("scrape-user", help="Scrape all threads by a user")
    p_user.add_argument("user", help="User ID or name")
    p_user.add_argument("-o", "--output", required=True, help="Output directory")
    p_user.add_argument("-c", "--concurrency", type=int, help="Max concurrent downloads")
    p_user.set_defaults(func=cmd_scrape_user)

    # tieba merge
    p_merge = sub.add_parser("merge", help="Merge scraped data into master.db")
    p_merge.add_argument("-s", "--source", required=True, help="Source scraped data directory")
    p_merge.add_argument("-o", "--output", required=True, help="Output archive directory")
    p_merge.add_argument("-f", "--forum", help="Process only this forum")
    p_merge.set_defaults(func=cmd_merge)

    # tieba pack
    p_pack = sub.add_parser("pack", help="Pack media into tar archives")
    p_pack.add_argument("-s", "--source", required=True, help="Source scraped data directory")
    p_pack.add_argument("-o", "--output", required=True, help="Output archive directory")
    p_pack.add_argument("-f", "--forum", help="Process only this forum")
    p_pack.set_defaults(func=cmd_pack)

    # tieba par2
    p_par2 = sub.add_parser("par2", help="Generate PAR2 parity files")
    p_par2.add_argument("-d", "--dir", required=True, help="Directory containing tar files")
    p_par2.add_argument("-r", "--redundancy", type=int, help="Redundancy percentage (default 5)")
    p_par2.set_defaults(func=cmd_par2)

    # tieba pipeline
    p_all = sub.add_parser("pipeline", help="Run full consolidation pipeline")
    p_all.add_argument("-s", "--source", required=True, help="Source scraped data directory")
    p_all.add_argument("-o", "--output", required=True, help="Output archive directory")
    p_all.add_argument("--skip-media", action="store_true", help="Skip media packing")
    p_all.add_argument("--skip-par2", action="store_true", help="Skip PAR2 generation")
    p_all.set_defaults(func=cmd_pipeline)

    # tieba serve
    p_serve = sub.add_parser("serve", help="Start the local reader server")
    p_serve.add_argument("data_dir", help="Directory containing forum archives")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8900, help="Bind port (default: 8900)")
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
