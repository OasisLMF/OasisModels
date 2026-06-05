#!/usr/bin/env python3
"""
Scan all *.csv files under a root directory for an OEDVersion column and
set every value in that column to a target version string.

Usage:
    python set_oed_version.py [--version 5.0.0] [--root .] [--dry-run]
"""

import argparse
import csv
import io
import os
import sys


def process_file(path: str, version: str, dry_run: bool) -> bool:
    """Return True if the file contained an OEDVersion column."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        content = fh.read()

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None or "OEDVersion" not in reader.fieldnames:
        return False

    rows = list(reader)
    for row in rows:
        row["OEDVersion"] = version

    if dry_run:
        print(f"  [dry-run] would update: {path}")
        return True

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(out.getvalue())

    print(f"  updated: {path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Set OEDVersion in all CSV files.")
    parser.add_argument("--version", default="5.0.0", help="Target OED version string (default: 5.0.0)")
    parser.add_argument("--root", default=".", help="Root directory to scan (default: current dir)")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would be changed without writing")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    print(f"Scanning {root} for CSV files with OEDVersion column ...")
    if args.dry_run:
        print("(dry-run mode — no files will be written)\n")

    updated = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".csv"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                if process_file(path, args.version, args.dry_run):
                    updated.append(path)
            except Exception as exc:
                print(f"  WARNING: could not process {path}: {exc}", file=sys.stderr)

    print(f"\n{'Would update' if args.dry_run else 'Updated'} {len(updated)} file(s).")


if __name__ == "__main__":
    main()
