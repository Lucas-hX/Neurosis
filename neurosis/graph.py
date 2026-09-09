"""Deterministic interaction graph and known-origin analysis from Lab events."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any
from uuid import UUID

from neurosis.lab import NeurosisEvent


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def entity_key(entity_type: str, entity_id: str) -> str:
    return f'{entity_type}:{entity_id}'


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    entity_id: str

    def document(self) -> dict[str, str]:
        return {'id': self.id, 'type': self.type, 'entity_id': self.entity_id}


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source: str
    target: str
    relation: str
    supporting_event_ids: tuple[str, ...]
    evidence_kinds: tuple[str, ...]
    recorder_ids: tuple[str, ...]

    def document(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'source': self.source,
            'target': self.target,
            'relation': self.relation,
            'supporting_event_ids': list(self.supporting_event_ids),
            'evidence_kinds': list(self.evidence_kinds),
            'recorder_ids': list(self.recorder_ids),
        }


@dataclass(frozen=True)
class ConsensusAnalysis:
    claim_id: str
    apparent_consensus: int
    known_origin_count: int | None
    cir: float | None
    supporting_event_ids: tuple[str, ...]
    missing_provenance_event_ids: tuple[str, ...]

    def document(self) -> dict[str, Any]:
        return {
            'claim_id': self.claim_id,
            'apparent_consensus': self.apparent_consensus,
            'known_origin_count': self.known_origin_count,
            'cir': self.cir,
            'supporting_event_ids': list(self.supporting_event_ids),
            'missing_provenance_event_ids': list(self.missing_provenance_event_ids),
        }


@dataclass(frozen=True)
class InteractionGraph:
    schema_version: str
    run_id: str
    population_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    missing_parent_event_ids: tuple[str, ...]
    unknown_origin_event_ids: tuple[str, ...]

    def document(self) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'population_id': self.population_id,
            'nodes': [item.document() for item in self.nodes],
            'edges': [item.document() for item in self.edges],
            'missing_parent_event_ids': list(self.missing_parent_event_ids),
            'unknown_origin_event_ids': list(self.unknown_origin_event_ids),
            'interpretation': ('Edges reproduce recorded relationships and provenance assertions; '
                               'they do not establish causal effect from timing alone.'),
        }

    def canonical_json(self) -> str:
        return _canonical(self.document())

    def ancestors(self, node_id: str) -> tuple[str, ...]:
        reverse: dict[str, set[str]] = {}
        for edge in self.edges:
            reverse.setdefault(edge.target, set()).add(edge.source)
        found: set[str] = set()
        pending = list(reverse.get(node_id, ()))
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.add(current)
            pending.extend(reverse.get(current, ()))
        return tuple(sorted(found))

    def common_ancestors(self, *node_ids: str) -> tuple[str, ...]:
        if not node_ids:
            return ()
        groups = [set(self.ancestors(node_id)) for node_id in node_ids]
        return tuple(sorted(set.intersection(*groups)))

    def max_depth_from(self, source_id: str) -> int | None:
        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
        if source_id not in {node.id for node in self.nodes}:
            return None
        pending = [(source_id, 0)]
        distance: dict[str, int] = {source_id: 0}
        while pending:
            current, depth = pending.pop(0)
            for target in sorted(adjacency.get(current, ())):
                if target not in distance:
                    distance[target] = depth + 1
                    pending.append((target, depth + 1))
        return max(distance.values())


_RELATIONS = {
    'agent_started': 'starts',
    'agent_stopped': 'stops',
    'agent_spawned': 'spawns',
    'model_requested': 'requests',
    'model_responded': 'responds',
    'model_failed': 'fails',
    'message_read': 'reads',
    'message_written': 'writes',
    'memory_read': 'reads',
    'memory_written': 'writes',
    'artifact_read': 'reads',
    'artifact_written': 'writes',
    'resource_read': 'reads',
    'resource_written': 'writes',
    'claim_observed': 'observes',
    'claim_adopted': 'adopts',
    'claim_rejected': 'rejects',
    'claim_verified': 'verifies',
    'claim_corrected': 'corrects',
    'tool_called': 'calls',
    'network_requested': 'requests',
}


def build_graph(events: list[NeurosisEvent]) -> InteractionGraph:
    if not events:
        raise ValueError('Cannot build a graph without events')
    run_ids = {event.run_id for event in events}
    population_ids = {event.population_id for event in events}
    if len(run_ids) != 1 or len(population_ids) != 1:
        raise ValueError('Graph input must contain one run and population')

    unique_events: dict[UUID, NeurosisEvent] = {}
    for event in events:
        old = unique_events.get(event.event_id)
        if old is not None and old != event:
            raise ValueError('Conflicting duplicate event ID')
        unique_events[event.event_id] = event

    nodes: dict[str, GraphNode] = {}
    edge_parts: dict[tuple[str, str, str], dict[str, set[str]]] = {}
    unknown_origins: set[str] = set()

    def add_node(node_type: str, node_id: str) -> str:
        key = entity_key(node_type, node_id)
        nodes[key] = GraphNode(key, node_type, node_id)
        return key

    def add_edge(source: str, target: str, relation: str, event: NeurosisEvent) -> None:
        part = edge_parts.setdefault((source, target, relation), {
            'events': set(), 'kinds': set(), 'recorders': set()})
        part['events'].add(str(event.event_id))
        part['kinds'].add(event.provenance.kind)
        part['recorders'].add(event.provenance.recorder_id)

    for event in unique_events.values():
        source = add_node(event.source.type, event.source.id)
        target = add_node(event.target.type, event.target.id)
        add_edge(source, target, _RELATIONS[event.event_type], event)
        if event.claim_id:
            add_node('claim', event.claim_id)
        if event.provenance.origin_ids is not None:
            for origin_id in event.provenance.origin_ids:
                origin = add_node('origin', origin_id)
                add_edge(origin, target, 'originates', event)
        elif event.event_type == 'message_written':
            unknown_origins.add(str(event.event_id))
        if event.event_type == 'message_written':
            references = event.metadata.get('reference_ids', [])
            if isinstance(references, list):
                for reference_id in references:
                    if isinstance(reference_id, str):
                        reference = add_node('message', reference_id)
                        add_edge(reference, target, 'references', event)

    known_event_ids = set(unique_events)
    missing_parents = {
        str(parent)
        for event in unique_events.values()
        for parent in event.provenance.parent_event_ids
        if parent not in known_event_ids
    }
    edges = []
    for (source, target, relation), part in edge_parts.items():
        identity = hashlib.sha256(f'{source}\0{relation}\0{target}'.encode()).hexdigest()
        edges.append(GraphEdge(
            identity, source, target, relation,
            tuple(sorted(part['events'])), tuple(sorted(part['kinds'])),
            tuple(sorted(part['recorders'])),
        ))
    return InteractionGraph(
        '0', str(next(iter(run_ids))), str(next(iter(population_ids))),
        tuple(nodes[key] for key in sorted(nodes)),
        tuple(sorted(edges, key=lambda item: (item.source, item.relation, item.target))),
        tuple(sorted(missing_parents)), tuple(sorted(unknown_origins)),
    )


def analyze_consensus(events: list[NeurosisEvent], claim_id: str) -> ConsensusAnalysis:
    supporting = [event for event in events
                  if event.event_type == 'message_written' and event.claim_id == claim_id]
    agents = {event.source.id for event in supporting if event.source.type == 'agent'}
    missing = [str(event.event_id) for event in supporting
               if event.provenance.origin_ids is None]
    known_origin_count: int | None
    if missing:
        known_origin_count = None
    else:
        known_origin_count = len({origin for event in supporting
                                  for origin in event.provenance.origin_ids or []})
    apparent_consensus = len(agents)
    cir = (known_origin_count / apparent_consensus
           if known_origin_count is not None and apparent_consensus else None)
    return ConsensusAnalysis(
        claim_id, apparent_consensus, known_origin_count, cir,
        tuple(sorted(str(event.event_id) for event in supporting)),
        tuple(sorted(missing)),
    )
