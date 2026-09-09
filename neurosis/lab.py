"""Provider-neutral Lab contracts and local recorder. Never imported by the HTTP app."""
import json
from typing import Annotated, Literal
from uuid import UUID

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')]
ModelIdentifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)

    def canonical_json(self):
        return json.dumps(self.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), allow_nan=False)


class ModelConfiguration(Contract):
    provider: Identifier
    model: ModelIdentifier
    model_version: Annotated[str, Field(min_length=1, max_length=256)]
    temperature: Annotated[float, Field(ge=0)]
    token_budget: Annotated[int, Field(strict=True, gt=0)]
    system_prompt_hash: Digest
    agent_prompt_hash: Digest


class RunManifest(Contract):
    schema_version: Literal['0'] = '0'
    track: Literal['lab'] = 'lab'
    synthetic: Literal[True] = True
    experiment_id: Annotated[str, Field(pattern=r'^EXP-[0-9]{3}$')]
    experiment_version: Identifier
    run_id: UUID
    population_id: UUID
    git_commit: Annotated[str, Field(pattern=r'^[a-f0-9]{40}$')]
    seed: Annotated[int, Field(strict=True, ge=0)]
    models: Annotated[list[ModelConfiguration], Field(min_length=1)]
    population_size: Annotated[int, Field(strict=True, gt=0)]
    topology: Identifier
    adversarial_fraction: Annotated[float, Field(ge=0, le=1)]
    declared_channels: list[Identifier]
    shared_resources: list[Identifier]
    environment_version: Identifier
    config_hash: Digest
    start_time: AwareDatetime
    end_time: AwareDatetime
    outcome: Literal['completed', 'failed', 'cancelled']

    @model_validator(mode='after')
    def interval(self):
        if self.end_time < self.start_time:
            raise ValueError('end_time precedes start_time')
        return self


class Entity(Contract):
    type: Identifier
    id: Identifier


class Provenance(Contract):
    kind: Literal['observed', 'agent_reported', 'inferred', 'unknown']
    recorder_id: Identifier
    parent_event_ids: list[UUID] = Field(default_factory=list)
    # Independent origins require controlled ground truth; absence means unknown.
    origin_ids: list[Identifier] | None = None


class NeurosisEvent(Contract):
    schema_version: Literal['0'] = '0'
    event_id: UUID
    timestamp: AwareDatetime
    experiment_id: Annotated[str, Field(pattern=r'^EXP-[0-9]{3}$')]
    run_id: UUID
    population_id: UUID
    agent_id: Identifier
    parent_agent_id: Identifier | None = None
    principal_id: Identifier | None = None
    model: ModelIdentifier
    provider: Identifier
    sandbox_id: Identifier
    event_type: Literal['agent_started', 'agent_stopped', 'agent_spawned',
                        'model_requested', 'model_responded', 'model_failed',
                        'message_read', 'message_written', 'memory_read', 'memory_written',
                        'artifact_read', 'artifact_written', 'resource_read', 'resource_written',
                        'claim_observed', 'claim_adopted', 'claim_rejected', 'claim_verified',
                        'claim_corrected', 'tool_called', 'network_requested']
    source: Entity
    target: Entity
    resource_id: Identifier | None = None
    artifact_id: Identifier | None = None
    memory_id: Identifier | None = None
    claim_id: Identifier | None = None
    content_hash: Digest | None = None
    declared_channel: Identifier | None = None
    provenance: Provenance
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def ancestry(self):
        parents = self.provenance.parent_event_ids
        if self.event_id in parents or len(set(parents)) != len(parents):
            raise ValueError('Parent events must be unique and cannot reference self')
        return self


def register_run(conn, manifest: RunManifest):
    """Register a concluded run; use an outer transaction to import a whole bundle."""
    manifest = RunManifest.model_validate_json(manifest.canonical_json())
    with conn.transaction():
        conn.execute('INSERT INTO lab.runs(run_id,experiment_id,population_id,manifest) VALUES (%s,%s,%s,%s)',
                     (manifest.run_id, manifest.experiment_id, manifest.population_id,
                      Jsonb(manifest.model_dump(mode='json'))))


def append_event(conn, event: NeurosisEvent):
    """Append in parent-before-child order. Exact retries return False; conflicts fail."""
    event = NeurosisEvent.model_validate_json(event.canonical_json())
    with conn.transaction():
        # Serialize writers for this run, including ancestry and duplicate checks.
        row = conn.execute('SELECT manifest FROM lab.runs WHERE run_id=%s FOR UPDATE', (event.run_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown run')
        manifest = RunManifest.model_validate(row[0])
        if (event.experiment_id, event.population_id) != (manifest.experiment_id, manifest.population_id):
            raise ValueError('Event association differs from run')
        if not manifest.start_time <= event.timestamp <= manifest.end_time:
            raise ValueError('Event timestamp outside run interval')
        if (event.provider, event.model) not in {(m.provider, m.model) for m in manifest.models}:
            raise ValueError('Event model is not declared in manifest')
        if event.declared_channel is not None and event.declared_channel not in manifest.declared_channels:
            raise ValueError('Unknown declared channel')
        payload = event.model_dump(mode='json')
        old = conn.execute('SELECT payload FROM lab.events WHERE event_id=%s', (event.event_id,)).fetchone()
        if old:
            if old[0] != payload:
                raise ValueError('Immutable event ID conflict')
            return False
        for parent in event.provenance.parent_event_ids:
            parent_row = conn.execute('SELECT run_id,timestamp FROM lab.events WHERE event_id=%s', (parent,)).fetchone()
            if parent_row is None or parent_row[0] != event.run_id or parent_row[1] > event.timestamp:
                raise ValueError('Parent must be an earlier event in this run')
        conn.execute('INSERT INTO lab.events(event_id,run_id,experiment_id,population_id,timestamp,payload) VALUES (%s,%s,%s,%s,%s,%s)',
                     (event.event_id,event.run_id,event.experiment_id,event.population_id,event.timestamp,Jsonb(payload)))
        return True


def export_events(conn, run_id: UUID):
    """Deterministic JSONL in recorder order. No public HTTP export surface."""
    if not conn.execute('SELECT 1 FROM lab.runs WHERE run_id=%s', (run_id,)).fetchone():
        raise ValueError('Unknown run')
    with conn.cursor() as cursor:
        cursor.execute('SELECT payload FROM lab.events WHERE run_id=%s ORDER BY sequence', (run_id,))
        for row in cursor:
            yield NeurosisEvent.model_validate(row[0]).canonical_json() + '\n'


def main():
    import argparse
    import os
    from pathlib import Path
    import sys
    import psycopg

    parser = argparse.ArgumentParser(description='Local Lab artifact recorder; no model calls or public writes.')
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest', help='Atomically import a concluded run and canonical JSONL events')
    ingest.add_argument('manifest', type=Path)
    ingest.add_argument('events', type=Path)
    export = sub.add_parser('export', help='Write canonical events JSONL to stdout')
    export.add_argument('run_id', type=UUID)
    args = parser.parse_args()
    # Deliberately never fall back to the public application DATABASE_URL.
    with psycopg.connect(os.environ['LAB_DATABASE_URL']) as conn, conn.transaction():
        if args.command == 'ingest':
            manifest = RunManifest.model_validate_json(args.manifest.read_text())
            register_run(conn, manifest)
            with args.events.open() as stream:
                for line in stream:
                    event = NeurosisEvent.model_validate_json(line)
                    if event.run_id != manifest.run_id:
                        raise ValueError('Input contains a different run')
                    append_event(conn, event)
        else:
            for line in export_events(conn, args.run_id):
                sys.stdout.write(line)


if __name__ == '__main__':
    main()
