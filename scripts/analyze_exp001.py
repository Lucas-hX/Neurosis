#!/usr/bin/env python3
"""Regenerate EXP-001 graphs and metrics without model calls."""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neurosis.exp001 import (
    _finalize_schedule, _write_new, canonical, evaluation_csv, replay_trial,
)
from neurosis.report import render_trial_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Replay EXP-001 evaluation from immutable trial artifacts.')
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source_trials = args.source / 'trials'
    if not source_trials.is_dir():
        parser.error('source must be an EXP-001 schedule bundle containing trials/')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    metrics = []
    for source in sorted(path for path in source_trials.iterdir() if path.is_dir()):
        evaluation, graph = replay_trial(source)
        destination = args.output / 'trials' / source.name
        _write_new(destination / 'graph.json', graph.canonical_json() + '\n')
        _write_new(destination / 'metrics.json', canonical(evaluation) + '\n')
        _write_new(destination / 'results.csv', evaluation_csv(evaluation))
        _write_new(destination / 'report.html', render_trial_report(evaluation, graph))
        metrics.append(evaluation)
    comparison = {}
    for source in sorted(path for path in source_trials.iterdir() if path.is_dir()):
        destination = args.output / 'trials' / source.name
        comparison[source.name] = {
            name: ((source / name).is_file()
                   and hashlib.sha256((destination / name).read_bytes()).hexdigest()
                   == hashlib.sha256((source / name).read_bytes()).hexdigest())
            for name in ('graph.json', 'metrics.json', 'results.csv', 'report.html')
        }
    _write_new(args.output / 'replay-comparison.json', canonical(comparison) + '\n')
    schedule = __import__('json').loads((args.source / 'schedule.json').read_text())
    _finalize_schedule(args.output, metrics, 'recorded-replay', schedule['seeds'])
    print(canonical({'trials': len(metrics),
                     'all_artifacts_match': all(all(item.values())
                                                for item in comparison.values()),
                     'output': str(args.output)}))


if __name__ == '__main__':
    main()
