"""Bounded provider-neutral Lab harness. Never import this from the public app."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
from typing import Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import JsonValue

from neurosis.lab import Entity, ModelConfiguration, NeurosisEvent, Provenance, RunManifest


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class Message:
    role: Literal['user', 'assistant']
    content: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0 or self.cost_usd < 0:
            raise ValueError('Usage values cannot be negative')

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Reservation:
    tokens: int
    cost_usd: Decimal

    def __post_init__(self) -> None:
        if self.tokens < 1 or self.cost_usd < 0:
            raise ValueError('Invalid budget reservation')


@dataclass(frozen=True)
class AdapterRequest:
    agent_id: str
    turn: int
    attempt: int
    seed: int
    system_prompt: str
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class AdapterResponse:
    text: str
    response_id: str
    model: str
    model_version: str
    usage: Usage
    finish_reason: str = 'stop'
    service_tier: str | None = None


class AdapterError(Exception):
    def __init__(self, message: str, *, transient: bool, charge_reservation: bool = False):
        super().__init__(message)
        self.transient = transient
        self.charge_reservation = charge_reservation


class BudgetAccountingError(RuntimeError):
    pass


class ModelAdapter(Protocol):
    provider: str
    model: str
    model_version: str
    temperature: float
    max_output_tokens: int

    def settings(self) -> dict[str, JsonValue]: ...
    def reserve(self, request: AdapterRequest) -> Reservation: ...
    async def complete(self, request: AdapterRequest) -> AdapterResponse: ...


NextPrompt = Callable[['LogicalAgent', AdapterResponse], str | None | Awaitable[str | None]]
EventHook = Callable[[NeurosisEvent], None | Awaitable[None]]


@dataclass
class LogicalAgent:
    agent_id: str
    adapter: ModelAdapter
    system_prompt: str
    agent_prompt: str
    state: dict[str, JsonValue] = field(default_factory=dict)
    context: list[Message] = field(default_factory=list)
    max_turns: int = 1
    next_prompt: NextPrompt | None = None
    parent_agent_id: str | None = None
    principal_id: str | None = None
    sandbox_id: str = 'lab-local'

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError('max_turns must be positive')


@dataclass(frozen=True)
class RunPlan:
    experiment_id: str
    experiment_version: str
    git_commit: str
    seed: int
    environment_version: str
    topology: str = 'isolated'
    adversarial_fraction: float = 0
    declared_channels: tuple[str, ...] = ()
    shared_resources: tuple[str, ...] = ()
    source_worktree_dirty: bool = False
    source_diff_hash: str | None = None
    run_id: UUID = field(default_factory=uuid4)
    population_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RunnerLimits:
    max_concurrency: int = 4
    request_timeout_seconds: float = 60
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25
    request_ceiling: int = 1_000
    token_ceiling: int = 2_000_000
    monetary_ceiling_usd: Decimal = Decimal('5')

    def __post_init__(self) -> None:
        if min(self.max_concurrency, self.request_ceiling, self.token_ceiling) < 1:
            raise ValueError('Concurrency, request and token ceilings must be positive')
        if self.request_timeout_seconds <= 0 or self.max_retries < 0 or self.retry_backoff_seconds < 0:
            raise ValueError('Invalid timeout, retry, or backoff setting')
        if self.monetary_ceiling_usd < 0:
            raise ValueError('Monetary ceiling cannot be negative')

    def document(self) -> dict[str, JsonValue]:
        return {
            'max_concurrency': self.max_concurrency,
            'request_timeout_seconds': self.request_timeout_seconds,
            'max_retries': self.max_retries,
            'retry_backoff_seconds': self.retry_backoff_seconds,
            'request_ceiling': self.request_ceiling,
            'token_ceiling': self.token_ceiling,
            'monetary_ceiling_usd': str(self.monetary_ceiling_usd),
        }


@dataclass(frozen=True)
class AgentResult:
    agent_id: str
    outcome: Literal['completed', 'failed', 'cancelled']
    turns: int
    attempts: int
    responses: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class RunResult:
    manifest: RunManifest
    agents: tuple[AgentResult, ...]
    requests: int
    usage: Usage
    stop_reason: str | None


class Recorder(Protocol):
    async def start(self, config: str, agents: Sequence[LogicalAgent]) -> None: ...
    async def record(self, event: NeurosisEvent) -> None: ...
    async def finish(self, result: RunResult) -> None: ...


class MemoryRecorder:
    def __init__(self) -> None:
        self.config: str | None = None
        self.events: list[NeurosisEvent] = []
        self.result: RunResult | None = None

    async def start(self, config: str, agents: Sequence[LogicalAgent]) -> None:
        self.config = config

    async def record(self, event: NeurosisEvent) -> None:
        self.events.append(event)

    async def finish(self, result: RunResult) -> None:
        self.result = result


class DirectoryRecorder:
    """Fsync every raw event, then add the concluded manifest last."""

    def __init__(self, path: Path):
        self.path = path
        self._stream = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _write_new(path: Path, text: str) -> None:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

    async def start(self, config: str, agents: Sequence[LogicalAgent]) -> None:
        self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
        prompts = self.path / 'prompts'
        prompts.mkdir(mode=0o700)
        self._write_new(self.path / 'config.json', config + '\n')
        prompt_bytes: dict[str, str] = {}
        assignments = []
        for agent in agents:
            system_hash, agent_hash = sha256(agent.system_prompt), sha256(agent.agent_prompt)
            prompt_bytes[system_hash] = agent.system_prompt
            prompt_bytes[agent_hash] = agent.agent_prompt
            assignments.append({
                'agent_id': agent.agent_id, 'parent_agent_id': agent.parent_agent_id,
                'principal_id': agent.principal_id, 'sandbox_id': agent.sandbox_id,
                'provider': agent.adapter.provider, 'model': agent.adapter.model,
                'system_prompt_hash': system_hash, 'agent_prompt_hash': agent_hash,
                'max_turns': agent.max_turns, 'initial_state': agent.state,
            })
        for digest, prompt in prompt_bytes.items():
            self._write_new(prompts / f'{digest}.txt', prompt)
        self._write_new(self.path / 'agents.json', canonical(assignments) + '\n')
        self._stream = (self.path / 'events.jsonl').open('x', encoding='utf-8')

    async def record(self, event: NeurosisEvent) -> None:
        if self._stream is None:
            raise RuntimeError('Recorder has not started')
        async with self._lock:
            self._stream.write(event.canonical_json() + '\n')
            self._stream.flush()
            os.fsync(self._stream.fileno())

    async def finish(self, result: RunResult) -> None:
        if self._stream is None:
            raise RuntimeError('Recorder has not started')
        self._stream.close()
        self._stream = None
        payload = {
            'requests': result.requests,
            'usage': {'input_tokens': result.usage.input_tokens,
                      'output_tokens': result.usage.output_tokens,
                      'cost_usd': str(result.usage.cost_usd)},
            'stop_reason': result.stop_reason,
            'agents': [vars(item) | {'responses': list(item.responses)} for item in result.agents],
        }
        self._write_new(self.path / 'results.json', canonical(payload) + '\n')
        self._write_new(self.path / 'manifest.json', result.manifest.canonical_json() + '\n')


class _Budget:
    def __init__(self, limits: RunnerLimits):
        self.limits = limits
        self.requests = self.input_tokens = self.output_tokens = 0
        self.cost = Decimal(0)
        self.reserved_tokens = 0
        self.reserved_cost = Decimal(0)
        self._lock = asyncio.Lock()

    async def reserve(self, amount: Reservation) -> bool:
        async with self._lock:
            if self.requests >= self.limits.request_ceiling:
                return False
            if self.input_tokens + self.output_tokens + self.reserved_tokens + amount.tokens > self.limits.token_ceiling:
                return False
            if self.cost + self.reserved_cost + amount.cost_usd > self.limits.monetary_ceiling_usd:
                return False
            self.requests += 1
            self.reserved_tokens += amount.tokens
            self.reserved_cost += amount.cost_usd
            return True

    async def settle(self, reserved: Reservation, used: Usage) -> None:
        async with self._lock:
            exceeded = used.total_tokens > reserved.tokens or used.cost_usd > reserved.cost_usd
            self.reserved_tokens -= reserved.tokens
            self.reserved_cost -= reserved.cost_usd
            self.input_tokens += used.input_tokens
            self.output_tokens += used.output_tokens
            self.cost += used.cost_usd
            if exceeded:
                raise BudgetAccountingError('Adapter usage exceeded its conservative reservation')


class PopulationRunner:
    def __init__(self, plan: RunPlan, limits: RunnerLimits, recorder: Recorder,
                 hooks: Sequence[EventHook] = ()):
        self.plan, self.limits, self.recorder = plan, limits, recorder
        self.hooks = tuple(hooks)
        self._stop = asyncio.Event()
        self._stop_reason: str | None = None

    def _config(self, agents: Sequence[LogicalAgent]) -> str:
        return canonical({
            'schema_version': '0',
            'plan': {
                'experiment_id': self.plan.experiment_id,
                'experiment_version': self.plan.experiment_version,
                'run_id': str(self.plan.run_id), 'population_id': str(self.plan.population_id),
                'git_commit': self.plan.git_commit, 'seed': self.plan.seed,
                'environment_version': self.plan.environment_version,
                'topology': self.plan.topology,
                'adversarial_fraction': self.plan.adversarial_fraction,
                'declared_channels': list(self.plan.declared_channels),
                'shared_resources': list(self.plan.shared_resources),
                'source_worktree_dirty': self.plan.source_worktree_dirty,
                'source_diff_hash': self.plan.source_diff_hash,
            },
            'limits': self.limits.document(),
            'adapters': [agent.adapter.settings() for agent in agents],
        })

    async def _emit(self, event: NeurosisEvent) -> None:
        await self.recorder.record(event)
        for hook in self.hooks:
            result = hook(event)
            if inspect.isawaitable(result):
                await result

    def _event(self, agent: LogicalAgent, event_type: str, source: Entity, target: Entity,
               *, parents: Sequence[UUID] = (), content: str | None = None,
               metadata: dict[str, JsonValue] | None = None) -> NeurosisEvent:
        return NeurosisEvent(
            event_id=uuid4(), timestamp=datetime.now(UTC), experiment_id=self.plan.experiment_id,
            run_id=self.plan.run_id, population_id=self.plan.population_id,
            agent_id=agent.agent_id, parent_agent_id=agent.parent_agent_id,
            principal_id=agent.principal_id, model=agent.adapter.model,
            provider=agent.adapter.provider, sandbox_id=agent.sandbox_id,
            event_type=event_type, source=source, target=target,
            content_hash=sha256(content) if content is not None else None,
            provenance=Provenance(kind='observed', recorder_id='population-harness-v0',
                                  parent_event_ids=list(parents)),
            metadata=metadata or {})

    @staticmethod
    def _model_entity(agent: LogicalAgent) -> Entity:
        return Entity(type='model', id=agent.adapter.model.replace('/', ':'))

    def _stop_all(self, reason: str) -> None:
        if not self._stop.is_set():
            self._stop_reason = reason
            self._stop.set()

    async def _call(self, adapter: ModelAdapter, request: AdapterRequest,
                    external_cancel: asyncio.Event | None) -> AdapterResponse:
        call = asyncio.create_task(adapter.complete(request))
        internal = asyncio.create_task(self._stop.wait())
        external = asyncio.create_task(external_cancel.wait()) if external_cancel else None
        waits = {call, internal, *([external] if external else [])}
        try:
            done, _ = await asyncio.wait(waits, timeout=self.limits.request_timeout_seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            if call in done:
                try:
                    return await call
                except AdapterError:
                    raise
                except Exception as exc:
                    raise AdapterError(type(exc).__name__, transient=False,
                                       charge_reservation=True) from exc
            call.cancel()
            await asyncio.gather(call, return_exceptions=True)
            if external and external in done:
                self._stop_all('external cancellation')
            if internal in done or (external and external in done):
                raise AdapterError('cancelled', transient=False, charge_reservation=True)
            raise AdapterError('request timeout', transient=True, charge_reservation=True)
        finally:
            internal.cancel()
            if external:
                external.cancel()
            await asyncio.gather(internal, *([external] if external else []), return_exceptions=True)

    async def _run_agent(self, agent: LogicalAgent, semaphore: asyncio.Semaphore,
                         budget: _Budget, external_cancel: asyncio.Event | None) -> AgentResult:
        started = self._event(agent, 'agent_started', Entity(type='runner', id='population'),
                              Entity(type='agent', id=agent.agent_id),
                              metadata={'state': agent.state, 'max_turns': agent.max_turns})
        await self._emit(started)
        turns = attempts = 0
        responses: list[str] = []
        current_prompt: str | None = agent.agent_prompt
        error: str | None = None
        outcome: Literal['completed', 'failed', 'cancelled'] = 'completed'
        last_parent = started.event_id
        try:
            while turns < agent.max_turns and current_prompt is not None:
                if self._stop.is_set() or (external_cancel and external_cancel.is_set()):
                    if external_cancel and external_cancel.is_set():
                        self._stop_all('external cancellation')
                    outcome, error = 'cancelled', self._stop_reason or 'cancelled'
                    break
                messages = tuple([*agent.context, Message('user', current_prompt)])
                response = None
                for attempt in range(1, self.limits.max_retries + 2):
                    request = AdapterRequest(agent.agent_id, turns + 1, attempt, self.plan.seed,
                                             agent.system_prompt, messages)
                    reservation = agent.adapter.reserve(request)
                    if not await budget.reserve(reservation):
                        self._stop_all('budget exhausted before request')
                        outcome, error = 'cancelled', self._stop_reason
                        break
                    attempts += 1
                    request_data = {
                        'turn': request.turn, 'attempt': attempt, 'seed': request.seed,
                        'system_prompt': request.system_prompt,
                        'messages': [vars(item) for item in messages],
                        'settings': agent.adapter.settings(),
                        'reservation': {'tokens': reservation.tokens,
                                        'cost_usd': str(reservation.cost_usd)},
                    }
                    requested = self._event(agent, 'model_requested',
                        Entity(type='agent', id=agent.agent_id), self._model_entity(agent),
                        parents=[last_parent], content=canonical(request_data), metadata=request_data)
                    await self._emit(requested)
                    try:
                        async with semaphore:
                            response = await self._call(agent.adapter, request, external_cancel)
                        await budget.settle(reservation, response.usage)
                        response_data = {
                            'turn': request.turn, 'attempt': attempt,
                            'response_id': response.response_id, 'text': response.text,
                            'response_model': response.model, 'model_version': response.model_version,
                            'finish_reason': response.finish_reason,
                            'service_tier': response.service_tier,
                            'usage': {'input_tokens': response.usage.input_tokens,
                                      'output_tokens': response.usage.output_tokens,
                                      'cost_usd': str(response.usage.cost_usd),
                                      'cost_basis': 'configured_list_price'},
                        }
                        terminal = self._event(agent, 'model_responded', self._model_entity(agent),
                            Entity(type='agent', id=agent.agent_id), parents=[requested.event_id],
                            content=response.text, metadata=response_data)
                        await self._emit(terminal)
                        last_parent = terminal.event_id
                        break
                    except BudgetAccountingError as exc:
                        failure = self._event(
                            agent, 'model_failed', self._model_entity(agent),
                            Entity(type='agent', id=agent.agent_id), parents=[requested.event_id],
                            metadata={'turn': request.turn, 'attempt': attempt,
                                      'error_type': type(exc).__name__, 'error': str(exc),
                                      'transient': False, 'reservation_charged': False,
                                      'reported_usage': {
                                          'input_tokens': response.usage.input_tokens,
                                          'output_tokens': response.usage.output_tokens,
                                          'cost_usd': str(response.usage.cost_usd)}})
                        await self._emit(failure)
                        last_parent = failure.event_id
                        response = None
                        self._stop_all('budget accounting failure')
                        outcome, error = 'failed', str(exc)
                        break
                    except AdapterError as exc:
                        charged = Usage(reservation.tokens, 0, reservation.cost_usd) if exc.charge_reservation else Usage()
                        await budget.settle(reservation, charged)
                        failure = self._event(agent, 'model_failed', self._model_entity(agent),
                            Entity(type='agent', id=agent.agent_id), parents=[requested.event_id],
                            metadata={'turn': request.turn, 'attempt': attempt,
                                      'error_type': type(exc).__name__, 'error': str(exc),
                                      'transient': exc.transient,
                                      'reservation_charged': exc.charge_reservation})
                        await self._emit(failure)
                        last_parent = failure.event_id
                        if self._stop.is_set():
                            outcome, error = 'cancelled', self._stop_reason or str(exc)
                            break
                        if not exc.transient or attempt > self.limits.max_retries:
                            outcome, error = 'failed', str(exc)
                            break
                        await asyncio.sleep(self.limits.retry_backoff_seconds * (2 ** (attempt - 1)))
                if response is None:
                    break
                responses.append(response.text)
                agent.context.extend([Message('user', current_prompt), Message('assistant', response.text)])
                turns += 1
                current_prompt = None
                if agent.next_prompt and turns < agent.max_turns:
                    current_prompt = agent.next_prompt(agent, response)
                    if inspect.isawaitable(current_prompt):
                        current_prompt = await current_prompt
        except Exception as exc:
            self._stop_all('instrumentation or accounting failure')
            outcome, error = 'failed', f'{type(exc).__name__}: {exc}'
        stopped = self._event(agent, 'agent_stopped', Entity(type='agent', id=agent.agent_id),
                              Entity(type='runner', id='population'), parents=[last_parent],
                              metadata={'outcome': outcome, 'turns': turns,
                                        'attempts': attempts, 'error': error})
        await self._emit(stopped)
        return AgentResult(agent.agent_id, outcome, turns, attempts, tuple(responses), error)

    async def run(self, agents: Sequence[LogicalAgent], *,
                  cancel_event: asyncio.Event | None = None) -> RunResult:
        if not agents:
            raise ValueError('At least one agent is required')
        if len({agent.agent_id for agent in agents}) != len(agents):
            raise ValueError('Agent IDs must be unique')
        config = self._config(agents)
        start_time = datetime.now(UTC)
        await self.recorder.start(config, agents)
        budget, semaphore = _Budget(self.limits), asyncio.Semaphore(self.limits.max_concurrency)
        results = tuple(await asyncio.gather(*[
            asyncio.create_task(self._run_agent(agent, semaphore, budget, cancel_event))
            for agent in agents]))
        end_time = datetime.now(UTC)
        outcome = ('failed' if any(item.outcome == 'failed' for item in results)
                   else 'cancelled' if any(item.outcome == 'cancelled' for item in results)
                   else 'completed')
        configurations: dict[str, ModelConfiguration] = {}
        for agent in agents:
            item = ModelConfiguration(
                provider=agent.adapter.provider, model=agent.adapter.model,
                model_version=agent.adapter.model_version, temperature=agent.adapter.temperature,
                token_budget=agent.adapter.max_output_tokens,
                system_prompt_hash=sha256(agent.system_prompt),
                agent_prompt_hash=sha256(agent.agent_prompt))
            configurations[item.canonical_json()] = item
        manifest = RunManifest(
            experiment_id=self.plan.experiment_id,
            experiment_version=self.plan.experiment_version,
            run_id=self.plan.run_id, population_id=self.plan.population_id,
            git_commit=self.plan.git_commit, seed=self.plan.seed,
            models=[configurations[key] for key in sorted(configurations)],
            population_size=len(agents), topology=self.plan.topology,
            adversarial_fraction=self.plan.adversarial_fraction,
            declared_channels=list(self.plan.declared_channels),
            shared_resources=list(self.plan.shared_resources),
            environment_version=self.plan.environment_version,
            config_hash=hashlib.sha256(config.encode()).hexdigest(),
            start_time=start_time, end_time=end_time, outcome=outcome)
        result = RunResult(manifest, results, budget.requests,
                           Usage(budget.input_tokens, budget.output_tokens, budget.cost),
                           self._stop_reason)
        await self.recorder.finish(result)
        return result


class DeterministicAdapter:
    """Credential-free adapter for concurrency, retry, timeout, and cancellation tests."""

    provider = 'fixture'
    model = 'deterministic'
    model_version = '0'
    temperature = 0.0

    def __init__(self, *, max_output_tokens: int = 32, delay_seconds: float = 0,
                 transient_attempts: frozenset[int] = frozenset()):
        self.max_output_tokens = max_output_tokens
        self.delay_seconds = delay_seconds
        self.transient_attempts = transient_attempts

    def settings(self) -> dict[str, JsonValue]:
        return {'provider': self.provider, 'model': self.model,
                'model_version': self.model_version, 'temperature': self.temperature,
                'max_output_tokens': self.max_output_tokens, 'fixture': True}

    def reserve(self, request: AdapterRequest) -> Reservation:
        return Reservation(64 + self.max_output_tokens, Decimal(0))

    async def complete(self, request: AdapterRequest) -> AdapterResponse:
        await asyncio.sleep(self.delay_seconds)
        if request.attempt in self.transient_attempts:
            raise AdapterError('scripted transient failure', transient=True)
        text = f'fixture:{request.agent_id}:turn-{request.turn}'
        return AdapterResponse(text, f'fixture-{request.agent_id}-{request.turn}', self.model,
                               self.model_version, Usage(32, 8, Decimal(0)))


class GroqAdapter:
    """Direct Groq Chat Completions adapter for the two pinned GPT-OSS models."""

    provider = 'groq'
    model_version = 'provider-version-unavailable'
    endpoint = 'https://api.groq.com/openai/v1/chat/completions'
    PRICES = {
        'openai/gpt-oss-20b': (Decimal('0.075'), Decimal('0.30')),
        'openai/gpt-oss-120b': (Decimal('0.15'), Decimal('0.60')),
    }

    def __init__(self, api_key: str, *, model: str, max_output_tokens: int = 2_000,
                 temperature: float = 0, reasoning_effort: Literal['low', 'medium', 'high'] = 'low',
                 service_tier: Literal['on_demand', 'flex', 'auto'] = 'on_demand',
                 client: httpx.AsyncClient | None = None):
        if model not in self.PRICES:
            raise ValueError(f'Unpriced Groq model: {model}')
        if not api_key:
            raise ValueError('GROQ_API_KEY is required')
        self.api_key, self.model = api_key, model
        self.max_output_tokens, self.temperature = max_output_tokens, temperature
        self.reasoning_effort, self.service_tier, self.client = reasoning_effort, service_tier, client

    def settings(self) -> dict[str, JsonValue]:
        input_price, output_price = self.PRICES[self.model]
        return {
            'provider': self.provider, 'endpoint': self.endpoint, 'model': self.model,
            'model_version': self.model_version, 'temperature': self.temperature,
            'max_output_tokens': self.max_output_tokens,
            'reasoning_effort': self.reasoning_effort, 'reasoning_format': 'hidden',
            'service_tier': self.service_tier, 'seeded_determinism': 'best-effort',
            'input_price_per_million_usd': str(input_price),
            'output_price_per_million_usd': str(output_price),
            'pricing_checked_on': '2026-09-09',
        }

    def reserve(self, request: AdapterRequest) -> Reservation:
        # UTF-8 bytes plus generous message framing is a conservative BPE token ceiling.
        input_ceiling = 256 + len(request.system_prompt.encode())
        input_ceiling += sum(64 + len(item.content.encode()) for item in request.messages)
        input_price, output_price = self.PRICES[self.model]
        cost = (Decimal(input_ceiling) * input_price
                + Decimal(self.max_output_tokens) * output_price) / Decimal(1_000_000)
        return Reservation(input_ceiling + self.max_output_tokens, cost)

    async def complete(self, request: AdapterRequest) -> AdapterResponse:
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': request.system_prompt},
                *({'role': item.role, 'content': item.content} for item in request.messages),
            ],
            'temperature': self.temperature,
            'max_completion_tokens': self.max_output_tokens,
            'reasoning_effort': self.reasoning_effort,
            'reasoning_format': 'hidden',
            'seed': request.seed,
            'service_tier': self.service_tier,
            'stream': False,
        }
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json',
                   'User-Agent': 'neurosis-lab-harness/0'}
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=None)
        try:
            response = await client.post(self.endpoint, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AdapterError(type(exc).__name__, transient=True, charge_reservation=True) from exc
        finally:
            if own_client:
                await client.aclose()
        if response.status_code >= 400:
            transient = response.status_code in {408, 409, 429} or response.status_code >= 500
            # Provider bodies can echo request details; do not copy them into events.
            raise AdapterError(f'Groq HTTP {response.status_code}', transient=transient,
                               charge_reservation=True)
        try:
            data = response.json()
            choice, usage_data = data['choices'][0], data['usage']
            text = choice['message']['content']
            if not isinstance(text, str):
                raise TypeError('response content is not text')
            usage = Usage(int(usage_data['prompt_tokens']), int(usage_data['completion_tokens']),
                          self._cost(usage_data))
            return AdapterResponse(
                text=text, response_id=str(data['id']), model=str(data['model']),
                model_version=str(data.get('system_fingerprint') or self.model_version),
                usage=usage, finish_reason=str(choice.get('finish_reason') or 'unknown'),
                service_tier=data.get('service_tier'))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AdapterError('Malformed Groq response', transient=False) from exc

    def _cost(self, usage: dict[str, object]) -> Decimal:
        input_price, output_price = self.PRICES[self.model]
        return (Decimal(int(usage['prompt_tokens'])) * input_price
                + Decimal(int(usage['completion_tokens'])) * output_price) / Decimal(1_000_000)


def _git_source() -> tuple[str, bool, str | None]:
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    status = subprocess.check_output(
        ['git', 'status', '--porcelain=v1', '--untracked-files=all'])
    if not status:
        return commit, False, None
    digest = hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD']))
    untracked = subprocess.check_output(
        ['git', 'ls-files', '--others', '--exclude-standard', '-z']).split(b'\0')
    for raw_path in sorted(item for item in untracked if item):
        path = Path(os.fsdecode(raw_path))
        digest.update(raw_path + b'\0')
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return commit, True, digest.hexdigest()


def _env_value(name: str) -> str:
    if value := os.getenv(name):
        return value
    path = Path('.env')
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            key, separator, value = line.partition('=')
            if separator and key.strip() == name:
                return value.strip().strip('"').strip("'")
    raise RuntimeError(f'{name} is not set')


async def _cli(args: argparse.Namespace) -> RunResult:
    commit, dirty, diff_hash = _git_source()
    plan = RunPlan(experiment_id='EXP-000', experiment_version='harness-diagnostic-v0',
                   git_commit=commit, seed=args.seed,
                   environment_version='population-harness-v0',
                   source_worktree_dirty=dirty, source_diff_hash=diff_hash)
    limits = RunnerLimits(
        max_concurrency=args.concurrency, request_timeout_seconds=args.timeout,
        max_retries=args.retries, request_ceiling=args.request_ceiling,
        token_ceiling=args.token_ceiling,
        monetary_ceiling_usd=Decimal(args.cost_ceiling))
    if args.provider == 'fixture':
        adapters = [DeterministicAdapter(delay_seconds=args.fixture_delay)
                    for _ in range(args.agents)]
        return await _run_diagnostic(plan, limits, adapters, args.output)
    async with httpx.AsyncClient(timeout=None) as client:
        adapter = GroqAdapter(_env_value('GROQ_API_KEY'), model=args.model,
                              max_output_tokens=args.max_output_tokens,
                              reasoning_effort=args.reasoning_effort, client=client)
        return await _run_diagnostic(plan, limits, [adapter] * args.agents, args.output)


async def _run_diagnostic(plan: RunPlan, limits: RunnerLimits,
                          adapters: Sequence[ModelAdapter], output: str) -> RunResult:
    agents = [LogicalAgent(agent_id=f'agent-{index:02d}', adapter=adapter,
                           system_prompt='You are a bounded synthetic Lab diagnostic agent.',
                           agent_prompt='Return exactly the word OK and nothing else.')
              for index, adapter in enumerate(adapters)]
    return await PopulationRunner(plan, limits, DirectoryRecorder(Path(output))).run(agents)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run bounded Lab harness diagnostics.')
    parser.add_argument('provider', choices=['fixture', 'groq'])
    parser.add_argument('output', help='New output directory; existing paths are rejected')
    parser.add_argument('--model', choices=sorted(GroqAdapter.PRICES),
                        default='openai/gpt-oss-20b')
    parser.add_argument('--agents', type=int, default=20)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--request-ceiling', type=int, default=100)
    parser.add_argument('--token-ceiling', type=int, default=100_000)
    parser.add_argument('--cost-ceiling', default='0.10')
    parser.add_argument('--max-output-tokens', type=int, default=64)
    parser.add_argument('--reasoning-effort', choices=['low', 'medium', 'high'], default='low')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--fixture-delay', type=float, default=0)
    args = parser.parse_args()
    result = asyncio.run(_cli(args))
    print(canonical({'run_id': str(result.manifest.run_id),
                     'outcome': result.manifest.outcome, 'requests': result.requests,
                     'tokens': result.usage.total_tokens,
                     'cost_usd': str(result.usage.cost_usd), 'output': args.output}))


if __name__ == '__main__':
    main()
