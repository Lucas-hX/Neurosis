import asyncio
from decimal import Decimal
import hashlib
import json
import subprocess
import sys

import pytest
import psycopg

from neurosis.exp001 import (
    CONDITIONS, PROTOCOL_PATH, ScriptedAdapter, TrialCondition, build_reports,
    fixture_target, generate_task, initial_prompt, run_schedule, run_trial, summarize,
)
from neurosis.lab import NeurosisEvent, RunManifest, append_event, register_run


def test_seeded_ledger_and_eight_matched_cells_are_frozen():
    first = generate_task(7)
    assert first == generate_task(7)
    assert first != generate_task(8)
    assert len(CONDITIONS) == 8
    statements = {
        condition.peer_claim: [item.statement for item in build_reports(first, condition)]
        for condition in CONDITIONS
    }
    assert len(statements) == 2
    for condition in CONDITIONS:
        reports = build_reports(first, condition)
        origins = {origin for report in reports for origin in report.origin_ids}
        assert len(origins) == (4 if condition.origin_structure == 'independent' else 1)


def test_hidden_prompt_omits_operator_lineage_and_explicit_prompt_shows_it():
    task = generate_task(0)
    hidden = TrialCondition('recycled', 'hidden', 'incorrect')
    explicit = TrialCondition('recycled', 'explicit', 'incorrect')
    hidden_prompt = initial_prompt(task, hidden, build_reports(task, hidden))
    explicit_prompt = initial_prompt(task, explicit, build_reports(task, explicit))
    assert 'observation-' not in hidden_prompt
    assert 'source_ids' not in hidden_prompt
    assert 'references' not in hidden_prompt
    assert 'observation-' in explicit_prompt
    assert 'source_ids' in explicit_prompt


def test_one_seed_fixture_builds_eight_complete_replayable_trial_bundles(tmp_path):
    destination = tmp_path / 'schedule'
    results = asyncio.run(run_schedule(destination, [0], 'fixture'))
    assert len(results) == 8
    assert all(result.manifest.outcome == 'completed' for result in results)
    assert all(result.manifest.population_size == 5 for result in results)
    assert all(result.usage.cost_usd == Decimal(0) for result in results)
    trials = sorted((destination / 'trials').iterdir())
    assert len(trials) == 8
    for trial in trials:
        assert {'manifest.json', 'events.jsonl', 'graph.json', 'metrics.json',
                'trial.json', 'results.csv', 'report.html', 'SHA256SUMS'} <= {
                    item.name for item in trial.iterdir()}
        for line in (trial / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256((trial / name).read_bytes()).hexdigest() == digest
        events = [json.loads(line) for line in (trial / 'events.jsonl').read_text().splitlines()]
        target_start = next(index for index, event in enumerate(events)
                            if event['event_type'] == 'agent_started'
                            and event['agent_id'] == 'target')
        writes = [index for index, event in enumerate(events)
                  if event['event_type'] == 'message_written']
        assert len(writes) == 4 and max(writes) < target_start
        metrics = json.loads((trial / 'metrics.json').read_text())
        expected_origins = 4 if '-independent-' in trial.name else 1
        assert metrics['known_origin_count'] == expected_origins
        assert metrics['apparent_consensus'] == 4
        assert metrics['cir'] == expected_origins / 4
        if '-hidden-' in trial.name:
            agents = json.loads((trial / 'agents.json').read_text())
            target = next(item for item in agents if item['agent_id'] == 'target')
            prompt = (trial / 'prompts' / f"{target['agent_prompt_hash']}.txt").read_text()
            assert 'observation-' not in prompt and 'source_ids' not in prompt
    summary = json.loads((destination / 'summary.json').read_text())
    assert summary['scheduled_trials'] == 8
    assert summary['paired_contrasts']['difference_in_differences']['paired_seeds'] == 1
    assert '<script' not in (destination / 'report.html').read_text().lower()
    replay = tmp_path / 'replay'
    completed = subprocess.run(
        [sys.executable, 'scripts/analyze_exp001.py', str(destination), str(replay)],
        text=True, capture_output=True, check=True)
    assert json.loads(completed.stdout)['all_artifacts_match'] is True
    assert all(all(value.values()) for value in
               json.loads((replay / 'replay-comparison.json').read_text()).values())


def test_malformed_target_answer_is_recorded_and_not_scored(tmp_path):
    task = generate_task(0)
    condition = TrialCondition('recycled', 'hidden', 'incorrect')
    adapter = ScriptedAdapter('bad-target', {
        ('target', 1): 'not json',
        ('target', 2): '{"answer":"A"}',
    }, max_output_tokens=256)
    result = asyncio.run(run_trial(
        tmp_path / 'bad', 0, condition, adapter, git_commit='a' * 40))
    assert result.manifest.outcome == 'completed'
    metrics = json.loads((tmp_path / 'bad' / 'metrics.json').read_text())
    assert metrics['valid_final_answer'] is False
    assert metrics['false_belief_adoption'] is None
    assert metrics['answer_errors']['1']
    assert metrics['answer_errors']['2']


def test_complete_trial_imports_parent_before_child_into_lab_database(database, tmp_path):
    task = generate_task(2)
    condition = TrialCondition('recycled', 'explicit', 'incorrect')
    path = tmp_path / 'trial'
    asyncio.run(run_trial(path, 2, condition, fixture_target(task, condition),
                          git_commit='b' * 40))
    manifest = RunManifest.model_validate_json((path / 'manifest.json').read_text())
    events = [NeurosisEvent.model_validate_json(line)
              for line in (path / 'events.jsonl').read_text().splitlines()]
    with psycopg.connect(database['admin']) as connection:
        register_run(connection, manifest)
        assert all(append_event(connection, event) for event in events)


def test_protocol_pins_launch_gates_metrics_and_model():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert protocol['status'] == 'frozen-prepilot'
    assert protocol['schedule']['planned_pilot_trials'] == 160
    assert protocol['models']['target']['model'] == 'openai/gpt-oss-120b'
    assert protocol['limits']['max_provider_concurrency'] == 4
    assert protocol['limits']['pilot_cost_ceiling_usd'] == '2.00'
    assert protocol['primary_metric']['name'] == 'false_belief_adoption'
    assert protocol['uncertainty']['paired_contrasts'].startswith('seed-paired')


def test_summary_keeps_zero_denominators_and_missing_pairs_undefined():
    summary = summarize([])
    assert all(cell['rate'] is None and cell['wilson_95'] is None
               for cell in summary['cells'].values())
    assert all(contrast['mean_difference'] is None
               for contrast in summary['paired_contrasts'].values())
