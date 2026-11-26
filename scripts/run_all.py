"""Run the WHOLE engine (leave + attendance + payroll) and write all output files.

    python scripts/run_all.py --data data --out output
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from leave_attendance.pipeline import build, write_all   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--commands", default=None, help="defaults to <data>/commands.txt")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    needed = ["employees.csv", "holidays.csv", "leave_balances_opening.csv", "comp_off_credits.csv",
              "tax_params.csv", "it_slabs.csv", "pt_slabs.csv", "commands.txt"]
    missing = [n for n in needed if not os.path.exists(os.path.join(args.data, n))]
    if missing:
        raise SystemExit(f"Missing files in '{args.data}': {', '.join(missing)}")

    runner, engine = build(args.data)
    print("tax_params.csv -> how each parameter was found (check these!):")
    for name, key, value in engine.p.report:
        print(f"   {name:<18} <- {key:<28} = {value}")

    runner.run_file(args.commands or os.path.join(args.data, "commands.txt"))
    write_all(runner, engine, args.out)

    counts = {}
    for _, _, status, _, _ in runner.log:
        counts[status] = counts.get(status, 0) + 1
    print("\ncommands processed:", len(runner.log), counts)
    print("payslips          :", len(engine.payslips))
    print("F&F statements    :", len(engine.fnf))
    for status in ("PENDING", "APPROVED", "AUTO_APPROVED", "REJECTED", "CANCELLED"):
        n = sum(1 for r in runner.leave.requests.values() if r.status == status)
        print(f"   leave {status:<14}{n}")
    print("data issues       :", len(runner.data_issues))
    for i in runner.data_issues:
        print(f"   {os.path.basename(i.source)} line {i.line_no}: {i.kind}")
    for w in sorted(set(engine.warnings)):
        print("WARNING:", w)
    print("outputs written to:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
