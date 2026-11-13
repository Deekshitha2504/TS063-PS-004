"""Run the leave/attendance side over a command file and write the outputs.

    python scripts/run_leave.py --data data --out output
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from leave_attendance.commands import CommandRunner   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--commands", default=None, help="defaults to <data>/commands.txt")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    runner = CommandRunner(args.data)
    runner.run_file(args.commands or os.path.join(args.data, "commands.txt"))
    runner.write_outputs(args.out)

    counts = {}
    for _, _, status, _, _ in runner.log:
        counts[status] = counts.get(status, 0) + 1
    print("commands processed:", len(runner.log), counts)
    print("leave requests    :", len(runner.leave.order))
    for status in ("PENDING", "APPROVED", "AUTO_APPROVED", "REJECTED", "CANCELLED"):
        n = sum(1 for r in runner.leave.requests.values() if r.status == status)
        print(f"   {status:<14}{n}")
    print("data issues       :", len(runner.data_issues))
    for i in runner.data_issues:
        print(f"   {os.path.basename(i.source)} line {i.line_no}: {i.kind}")
    print("outputs written to:", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
