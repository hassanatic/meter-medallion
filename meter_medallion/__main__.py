import argparse
from pathlib import Path

from .pipeline import AssertionFailed, run
from .sample import generate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="meter-medallion")
    sub = parser.add_subparsers(dest="command", required=True)
    sample = sub.add_parser("sample", help="write deterministic synthetic source files")
    sample.add_argument("--out", type=Path, default=Path("data/sample"))
    run_cmd = sub.add_parser("run", help="load bronze and build every model")
    run_cmd.add_argument("--data", type=Path, default=Path("data/sample"))
    run_cmd.add_argument("--db", default="build/warehouse.db")
    args = parser.parse_args(argv)

    if args.command == "sample":
        print(generate(args.out))
        return 0

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.db).unlink(missing_ok=True)
    try:
        result = run(args.data, args.db)
    except AssertionFailed as e:
        print(f"assertion failed: {e}")
        return 1
    for name, count in result.row_counts.items():
        print(f"{name:32} {count:>7}")
    print(f"{len(result.built)} models built, {result.assertions_checked} assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
