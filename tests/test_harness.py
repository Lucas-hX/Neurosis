import asyncio
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

import httpx
import psycopg

from neurosis.harness import (
    AdapterRequest, AdapterResponse, DeterministicAdapter, DirectoryRecorder,
    GroqAdapter, LogicalAgent, MemoryRecorder, Message, PopulationRunner, RunPlan,
    RunnerLimits, Usage,
)
from neurosis.lab import NeurosisEvent, RunManifest, append_event, export_events, register_run


def plan():
    return RunPlan(experiment_id='EXP-000', experiment_version='test', git_commit='a' * 40,
                   seed=7, environment_version='harness-test')


def agents(adapter, count=1):
    return [LogicalAgent(f'agent-{index:02d}', adapter, 'system bytes', 'agent bytes')
            for index in range(count)]


class TrackingAdapter(DeterministicAdapter):
    def __init__(self):
        super().__init__(delay_seconds=0.005, transient_attempts=frozenset({1}))
        self.active = 0
        self.maximum = 0
        self.lock = asyncio.Lock()

    async def complete(self, request):
        async with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            return await super().complete(request)
        finally:
            async with self.lock:
                self.active -= 1


def test_twenty_agents_retry_with_bounded_concurrency():
    async def exercise():
        adapter, recorder = TrackingAdapter(), MemoryRecorder()
        result = await PopulationRunner(
            plan(), RunnerLimits(max_concurrency=4, retry_backoff_seconds=0), recorder
        ).run(agents(adapter, 20))
        assert result.manifest.outcome == 'completed'
        assert result.manifest.population_size == 20
        assert result.requests == 40
        assert adapter.maximum == 4
        assert all(item.attempts == 2 and item.turns == 1 for item in result.agents)
        assert sum(event.event_type == 'model_requested' for event in recorder.events) == 40
        assert sum(event.event_type == 'model_failed' for event in recorder.events) == 20
        assert sum(event.event_type == 'model_responded' for event in recorder.events) == 20
        assert len({event.event_id for event in recorder.events}) == len(recorder.events)
    asyncio.run(exercise())


def test_multi_turn_state_context_and_hook():
    async def exercise():
        seen = []

        def next_prompt(agent, response):
            agent.state['last'] = response.text
            return 'second prompt'

        agent = LogicalAgent('target', DeterministicAdapter(), 'system', 'first prompt',
                             state={'condition': 'hidden'}, max_turns=2,
                             next_prompt=next_prompt)
        recorder = MemoryRecorder()
        result = await PopulationRunner(plan(), RunnerLimits(), recorder,
                                        hooks=[lambda event: seen.append(event.event_type)]).run([agent])
        assert result.agents[0].turns == 2
        assert agent.state['last'] == 'fixture:target:turn-1'
        assert [item.role for item in agent.context] == ['user', 'assistant', 'user', 'assistant']
        assert seen == [event.event_type for event in recorder.events]
    asyncio.run(exercise())


def test_budget_and_external_cancellation_stop_scheduling():
    async def budget():
        recorder = MemoryRecorder()
        result = await PopulationRunner(
            plan(), RunnerLimits(token_ceiling=100, retry_backoff_seconds=0), recorder
        ).run(agents(DeterministicAdapter(delay_seconds=0.1), 5))
        assert result.manifest.outcome == 'cancelled'
        assert result.stop_reason == 'budget exhausted before request'
        assert result.usage.total_tokens <= 100

    async def cancellation():
        cancel = asyncio.Event()
        recorder = MemoryRecorder()
        task = asyncio.create_task(PopulationRunner(
            plan(), RunnerLimits(request_timeout_seconds=1), recorder
        ).run(agents(DeterministicAdapter(delay_seconds=1), 5), cancel_event=cancel))
        await asyncio.sleep(0.01)
        cancel.set()
        result = await task
        assert result.manifest.outcome == 'cancelled'
        assert result.stop_reason == 'external cancellation'
        assert all(item.outcome == 'cancelled' for item in result.agents)

    asyncio.run(budget())
    asyncio.run(cancellation())


def test_timeout_is_recorded_and_conservatively_charged():
    async def exercise():
        recorder = MemoryRecorder()
        result = await PopulationRunner(
            plan(), RunnerLimits(request_timeout_seconds=0.001, max_retries=0), recorder
        ).run(agents(DeterministicAdapter(delay_seconds=1)))
        assert result.manifest.outcome == 'failed'
        assert result.usage.total_tokens == 96
        failure = next(event for event in recorder.events if event.event_type == 'model_failed')
        assert failure.metadata['reservation_charged'] is True
        assert failure.metadata['error'] == 'request timeout'
    asyncio.run(exercise())


def test_usage_over_reservation_fails_and_records_reported_usage():
    class BadReservationAdapter(DeterministicAdapter):
        async def complete(self, request):
            response = await super().complete(request)
            return AdapterResponse(response.text, response.response_id, response.model,
                                   response.model_version, Usage(97, 0, Decimal(0)))

    async def exercise():
        recorder = MemoryRecorder()
        result = await PopulationRunner(plan(), RunnerLimits(), recorder).run(
            agents(BadReservationAdapter()))
        assert result.manifest.outcome == 'failed'
        assert result.stop_reason == 'budget accounting failure'
        assert result.usage.total_tokens == 97
        failure = next(event for event in recorder.events if event.event_type == 'model_failed')
        assert failure.metadata['error_type'] == 'BudgetAccountingError'
        assert failure.metadata['reported_usage']['input_tokens'] == 97
    asyncio.run(exercise())


def test_directory_recorder_stages_replayable_artifacts(tmp_path):
    async def exercise():
        destination = tmp_path / 'run'
        result = await PopulationRunner(
            plan(), RunnerLimits(), DirectoryRecorder(destination)
        ).run(agents(DeterministicAdapter(), 2))
        manifest = RunManifest.model_validate_json((destination / 'manifest.json').read_text())
        assert manifest == result.manifest
        config = (destination / 'config.json').read_text().rstrip('\n')
        assert manifest.config_hash == __import__('hashlib').sha256(config.encode()).hexdigest()
        event_lines = (destination / 'events.jsonl').read_text().splitlines()
        assert len(event_lines) == 8
        assert all(NeurosisEvent.model_validate_json(line) for line in event_lines)
        assignment = json.loads((destination / 'agents.json').read_text())[0]
        assert (destination / 'prompts' / f"{assignment['system_prompt_hash']}.txt").read_text() == 'system bytes'
        assert (destination / 'prompts' / f"{assignment['agent_prompt_hash']}.txt").read_text() == 'agent bytes'
        assert 'api_key' not in config.lower()
    asyncio.run(exercise())


def test_staged_harness_bundle_imports_into_lab_recorder(database, tmp_path):
    destination = tmp_path / 'importable-run'

    async def create_bundle():
        return await PopulationRunner(
            plan(), RunnerLimits(), DirectoryRecorder(destination)
        ).run(agents(DeterministicAdapter(), 2))

    result = asyncio.run(create_bundle())
    events = [NeurosisEvent.model_validate_json(line)
              for line in (destination / 'events.jsonl').read_text().splitlines()]
    with psycopg.connect(database['admin']) as connection:
        register_run(connection, result.manifest)
        assert all(append_event(connection, event) for event in events)
        assert list(export_events(connection, result.manifest.run_id)) == [
            event.canonical_json() + '\n' for event in events]


def test_groq_adapter_records_usage_fingerprint_and_never_serializes_key():
    async def exercise():
        seen = {}

        async def respond(request):
            seen['authorization'] = request.headers['Authorization']
            seen['payload'] = json.loads(request.content)
            return httpx.Response(200, json={
                'id': 'req-test', 'model': 'openai/gpt-oss-120b',
                'system_fingerprint': 'fp_test', 'service_tier': 'on_demand',
                'choices': [{'message': {'content': '{"answer":"A"}'},
                             'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                          'total_tokens': 120},
            })

        key = 'gsk_test_secret'
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        adapter = GroqAdapter(key, model='openai/gpt-oss-120b', max_output_tokens=64,
                              client=client)
        request = AdapterRequest('target', 1, 1, 7, 'system', (Message('user', 'prompt'),))
        response = await adapter.complete(request)
        await client.aclose()
        assert response.model_version == 'fp_test'
        assert response.usage == Usage(100, 20, Decimal('0.000027'))
        assert seen['payload']['seed'] == 7
        assert seen['payload']['reasoning_format'] == 'hidden'
        assert seen['authorization'] == f'Bearer {key}'
        assert key not in json.dumps(adapter.settings())
    asyncio.run(exercise())


def test_groq_error_classification():
    async def exercise():
        for status, transient in [(401, False), (429, True), (503, True)]:
            client = httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={'secret_echo': 'ignored'})))
            adapter = GroqAdapter('secret', model='openai/gpt-oss-20b', client=client)
            request = AdapterRequest('a', 1, 1, 0, 's', ())
            try:
                await adapter.complete(request)
                assert False, 'expected AdapterError'
            except Exception as exc:
                assert exc.transient is transient
                assert 'secret_echo' not in str(exc)
            await client.aclose()
    asyncio.run(exercise())


def test_public_bootstrap_filters_lab_credentials():
    bootstrap = Path('scripts/bootstrap.sh').read_text()
    assert "'REPOSITORY_URL'," in bootstrap
    assert "'GROQ_API_KEY'" not in bootstrap
    assert 'install -m 0600 .env /etc/neurosis/api.env.new' not in bootstrap
