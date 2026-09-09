"""Run-scoped instrumented board for controlled Lab experiments."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import inspect
from typing import Literal
from uuid import UUID, uuid4

from pydantic import JsonValue

from neurosis.lab import Entity, NeurosisEvent, Provenance


Visibility = Literal['explicit', 'hidden']
EventSink = Callable[[NeurosisEvent], None | Awaitable[None]]


@dataclass(frozen=True)
class BoardScope:
    experiment_id: str
    run_id: UUID
    population_id: UUID
    declared_channel: str = 'shared-board'
    resource_id: str = 'shared-board'


@dataclass(frozen=True)
class BoardActor:
    agent_id: str
    model: str
    provider: str
    sandbox_id: str
    parent_agent_id: str | None = None
    principal_id: str | None = None


@dataclass(frozen=True)
class BoardRecord:
    record_id: str
    author_agent_id: str
    claim_id: str
    statement: str
    origin_ids: tuple[str, ...] | None
    reference_ids: tuple[str, ...]
    write_event_id: UUID


@dataclass(frozen=True)
class BoardView:
    record_id: str
    payload: dict[str, JsonValue]
    read_event_id: UUID


class BoardIsolationError(ValueError):
    pass


class IsolatedBoard:
    """An in-process board whose only external effect is its supplied event sink."""

    def __init__(self, scope: BoardScope, visibility: Visibility, event_sink: EventSink, *,
                 clock: Callable[[], datetime] | None = None,
                 event_id_factory: Callable[[], UUID] | None = None):
        self.scope = scope
        self.visibility = visibility
        self._event_sink = event_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._event_id_factory = event_id_factory or uuid4
        self._records: dict[str, BoardRecord] = {}
        self._lock = asyncio.Lock()

    def _check_scope(self, scope: BoardScope) -> None:
        if scope != self.scope:
            raise BoardIsolationError('Cross-run or cross-population board access denied')

    async def _emit(self, event: NeurosisEvent) -> None:
        result = self._event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _event(self, actor: BoardActor, event_type: Literal['message_written', 'message_read'],
               source: Entity, target: Entity, *, event_id: UUID,
               parents: Sequence[UUID], record: BoardRecord | None,
               metadata: dict[str, JsonValue]) -> NeurosisEvent:
        return NeurosisEvent(
            event_id=event_id, timestamp=self._clock(), experiment_id=self.scope.experiment_id,
            run_id=self.scope.run_id, population_id=self.scope.population_id,
            agent_id=actor.agent_id, parent_agent_id=actor.parent_agent_id,
            principal_id=actor.principal_id, model=actor.model, provider=actor.provider,
            sandbox_id=actor.sandbox_id, event_type=event_type, source=source, target=target,
            resource_id=self.scope.resource_id,
            claim_id=record.claim_id if record else None,
            content_hash=(hashlib.sha256(record.statement.encode()).hexdigest()
                          if record else None),
            declared_channel=self.scope.declared_channel,
            provenance=Provenance(
                kind='observed', recorder_id='isolated-board-v0',
                parent_event_ids=list(parents),
                origin_ids=(list(record.origin_ids) if record and record.origin_ids is not None
                            else None)),
            metadata=metadata,
        )

    async def post(self, scope: BoardScope, actor: BoardActor, *, record_id: str,
                   claim_id: str, statement: str,
                   origin_ids: Sequence[str] | None,
                   reference_ids: Sequence[str] = ()) -> BoardRecord:
        self._check_scope(scope)
        async with self._lock:
            if record_id in self._records:
                raise ValueError(f'Duplicate board record: {record_id}')
            if not statement:
                raise ValueError('Board statement cannot be empty')
            if origin_ids is not None and len(set(origin_ids)) != len(origin_ids):
                raise ValueError('Origin IDs must be unique')
            references = tuple(reference_ids)
            if len(set(references)) != len(references):
                raise ValueError('Reference IDs must be unique')
            missing = [item for item in references if item not in self._records]
            if missing:
                raise ValueError(f'Unknown board references: {missing}')
            event_id = self._event_id_factory()
            record = BoardRecord(record_id, actor.agent_id, claim_id, statement,
                                 tuple(origin_ids) if origin_ids is not None else None,
                                 references, event_id)
            parents = [self._records[item].write_event_id for item in references]
            event = self._event(
                actor, 'message_written', Entity(type='agent', id=actor.agent_id),
                Entity(type='message', id=record_id), event_id=event_id, parents=parents,
                record=record,
                metadata={'reference_ids': list(references), 'board_visibility': self.visibility},
            )
            await self._emit(event)
            self._records[record_id] = record
            return record

    def render(self, record: BoardRecord) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            'peer_id': record.author_agent_id,
            'claim_id': record.claim_id,
            'statement': record.statement,
        }
        if self.visibility == 'explicit':
            payload['source_ids'] = (list(record.origin_ids)
                                     if record.origin_ids is not None else None)
            payload['references'] = list(record.reference_ids)
        return payload

    async def read(self, scope: BoardScope, actor: BoardActor, record_id: str) -> BoardView:
        self._check_scope(scope)
        async with self._lock:
            try:
                record = self._records[record_id]
            except KeyError as exc:
                raise KeyError(f'Unknown board record: {record_id}') from exc
            payload = self.render(record)
            event_id = self._event_id_factory()
            event = self._event(
                actor, 'message_read', Entity(type='message', id=record_id),
                Entity(type='agent', id=actor.agent_id), event_id=event_id,
                parents=[record.write_event_id], record=record,
                metadata={'view': payload, 'board_visibility': self.visibility},
            )
            await self._emit(event)
            return BoardView(record_id, payload, event_id)

    async def read_all(self, scope: BoardScope, actor: BoardActor) -> tuple[BoardView, ...]:
        return tuple([await self.read(scope, actor, record_id)
                      for record_id in sorted(self._records)])

    @property
    def records(self) -> tuple[BoardRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))
