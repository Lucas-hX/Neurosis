import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from neurosis.board import BoardActor, BoardIsolationError, BoardScope, IsolatedBoard
from neurosis.graph import analyze_consensus, build_graph
from neurosis.lab import Entity, NeurosisEvent, Provenance


def scope():
    return BoardScope('EXP-001', uuid4(), uuid4())


def actor(agent_id):
    return BoardActor(agent_id, 'scripted-reporter', 'fixture', 'trial-sandbox')


def test_board_is_run_scoped_and_hidden_view_cannot_leak_lineage():
    async def exercise():
        events = []
        own = scope()
        board = IsolatedBoard(own, 'hidden', events.append)
        record = await board.post(
            own, actor('reporter-00'), record_id='message-00', claim_id='claim-A',
            statement='The item is in A.', origin_ids=['private-origin-00'])
        view = await board.read(own, actor('target'), record.record_id)
        assert view.payload == {
            'peer_id': 'reporter-00', 'claim_id': 'claim-A',
            'statement': 'The item is in A.'}
        assert events[0].provenance.origin_ids == ['private-origin-00']
        assert events[1].metadata['view'] == view.payload
        assert all(event.run_id == own.run_id and event.population_id == own.population_id
                   for event in events)
        with pytest.raises(BoardIsolationError):
            await board.read(scope(), actor('target'), record.record_id)
    asyncio.run(exercise())


def test_explicit_view_and_references_preserve_parent_evidence():
    async def exercise():
        events = []
        own = scope()
        board = IsolatedBoard(own, 'explicit', events.append)
        first = await board.post(
            own, actor('reporter-00'), record_id='message-00', claim_id='claim-A',
            statement='The item is in A.', origin_ids=['origin-00'])
        second = await board.post(
            own, actor('reporter-01'), record_id='message-01', claim_id='claim-A',
            statement='I repeat the report.', origin_ids=['origin-00'],
            reference_ids=[first.record_id])
        view = await board.read(own, actor('target'), second.record_id)
        assert view.payload['source_ids'] == ['origin-00']
        assert view.payload['references'] == ['message-00']
        assert second.write_event_id in {event.event_id for event in events}
        written = next(event for event in events if event.event_id == second.write_event_id)
        assert written.provenance.parent_event_ids == [first.write_event_id]
    asyncio.run(exercise())


def board_events(origin_mode='independent', missing=False):
    async def exercise():
        events = []
        own = scope()
        board = IsolatedBoard(own, 'hidden', events.append)
        for index in range(4):
            origins = None if missing and index == 3 else [
                f'origin-{index if origin_mode == "independent" else 0}']
            await board.post(
                own, actor(f'reporter-{index}'), record_id=f'message-{index}',
                claim_id='claim-A', statement='The item is in A.', origin_ids=origins)
        for record in board.records:
            await board.read(own, actor('target'), record.record_id)
        decision = NeurosisEvent(
            event_id=uuid4(), timestamp=datetime.now(UTC), experiment_id=own.experiment_id,
            run_id=own.run_id, population_id=own.population_id, agent_id='target',
            model='scripted-target', provider='fixture', sandbox_id='trial-sandbox',
            event_type='claim_adopted', source=Entity(type='agent', id='target'),
            target=Entity(type='claim', id='claim-A'), claim_id='claim-A',
            provenance=Provenance(kind='observed', recorder_id='test'),
        )
        events.append(decision)
        return events
    return asyncio.run(exercise())


def test_graph_replay_known_origins_and_common_ancestors():
    independent = board_events('independent')
    repeated = board_events('recycled')
    assert analyze_consensus(independent, 'claim-A').known_origin_count == 4
    assert analyze_consensus(independent, 'claim-A').cir == 1
    repeated_analysis = analyze_consensus(repeated, 'claim-A')
    assert repeated_analysis.apparent_consensus == 4
    assert repeated_analysis.known_origin_count == 1
    assert repeated_analysis.cir == 0.25

    graph = build_graph(repeated)
    messages = [f'message:message-{index}' for index in range(4)]
    assert 'origin:origin-0' in graph.common_ancestors(*messages)
    assert graph.canonical_json() == build_graph(list(reversed(repeated))).canonical_json()
    assert graph.canonical_json() == build_graph(repeated + [repeated[0]]).canonical_json()
    assert 'agent:target' in graph.nodes[-1].id or any(
        node.id == 'agent:target' for node in graph.nodes)


def test_missing_provenance_and_parent_events_remain_explicitly_unknown():
    events = board_events(missing=True)
    analysis = analyze_consensus(events, 'claim-A')
    assert analysis.known_origin_count is None
    assert analysis.cir is None
    assert len(analysis.missing_provenance_event_ids) == 1
    orphan = events[-1].model_copy(update={
        'event_id': uuid4(),
        'provenance': Provenance(kind='observed', recorder_id='test',
                                 parent_event_ids=[uuid4()])})
    graph = build_graph(events + [orphan])
    assert len(graph.missing_parent_event_ids) == 1
