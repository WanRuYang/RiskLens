from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PROJECT_ROOT = PROJECT_ROOT / 'database'
VENV_PYTHON = PROJECT_ROOT / '.venv' / 'bin' / 'python'


def run(cmd: list[str], cwd: Path) -> int:
    print(f"\n$ (cd {cwd} && {' '.join(shlex.quote(part) for part in cmd)})", flush=True)
    completed = subprocess.run(cmd, cwd=str(cwd))
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the vNext benchmark suite for gemma4good.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--stage1', action='store_true')
    parser.add_argument('--stage2-raw', action='store_true')
    parser.add_argument('--stage2-grounded', action='store_true')
    parser.add_argument('--coverage-scan', action='store_true')
    parser.add_argument('--distribution', action='store_true')
    parser.add_argument('--provider', default='gemma', choices=['gemma', 'openai'])
    args = parser.parse_args()

    selected = any([
        args.stage1,
        args.stage2_raw,
        args.stage2_grounded,
        args.coverage_scan,
        args.distribution,
    ])
    if not selected:
        args.stage1 = True
        args.stage2_raw = True
        args.stage2_grounded = True
        args.coverage_scan = True
        args.distribution = True

    commands: list[tuple[list[str], Path]] = []
    if args.stage1:
        commands.append(([str(VENV_PYTHON), 'run_stage1_ocr_judge_benchmark.py', '--cases', 'benchmark_ocr_real_cases.json'], PROJECT_ROOT))
    if args.stage2_raw:
        commands.append(([str(VENV_PYTHON), 'run_stage2_text_benchmark.py'], PROJECT_ROOT))
    if args.stage2_grounded:
        commands.append(([str(VENV_PYTHON), 'run_stage2_grounded_benchmark.py', '--provider', args.provider], PROJECT_ROOT))
    if args.coverage_scan:
        commands.append((['python3', 'run_stage2_coverage_scan.py'], DATABASE_PROJECT_ROOT))
    if args.distribution:
        commands.append((['python3', 'analyze_stage2_score_distribution.py'], DATABASE_PROJECT_ROOT))

    print('Benchmark suite plan:', flush=True)
    for cmd, cwd in commands:
        print(f"- cwd={cwd} :: {' '.join(shlex.quote(part) for part in cmd)}", flush=True)

    if args.dry_run:
        return

    failures = 0
    for cmd, cwd in commands:
        failures += int(run(cmd, cwd) != 0)

    if failures:
        raise SystemExit(failures)


if __name__ == '__main__':
    main()
