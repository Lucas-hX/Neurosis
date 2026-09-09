import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from pydantic import ValidationError

from neurosis.admin import migrate
from neurosis.lab import RunManifest, NeurosisEvent, register_run, append_event, export_events


def manifest_data():
    now = datetime.now(timezone.utc)
    return dict(experiment_id='EXP-001', experiment_version='test-fixture', run_id=str(uuid4()),
                population_id=str(uuid4()), git_commit='a'*40, seed=0,
                models=[dict(provider='fixture', model='scripted', model_version='0', temperature=0,
                             token_budget=10, system_prompt_hash='a'*64, agent_prompt_hash='b'*64)],
                population_size=2, topology='board', adversarial_fraction=0,
                declared_channels=['board'], shared_resources=['board'], environment_version='fixture-0',
                config_hash='c'*64, start_time=now.isoformat(), end_time=(now+timedelta(seconds=10)).isoformat(),
                outcome='completed')


def event_data(manifest):
    return dict(event_id=str(uuid4()), timestamp=manifest.start_time.isoformat(),
                experiment_id=manifest.experiment_id, run_id=str(manifest.run_id), population_id=str(manifest.population_id),
                agent_id='a1', model='scripted', provider='fixture', sandbox_id='local', event_type='message_written',
                source={'type':'agent','id':'a1'}, target={'type':'message','id':'m1'}, declared_channel='board',
                provenance={'kind':'observed','recorder_id':'fixture'}, metadata={'synthetic_test': True})


def test_contract_validation():
    data = manifest_data()
    for field, bad in [('track','public'),('synthetic',False),('seed',True),('population_size',0),
                       ('adversarial_fraction',float('nan')),('start_time','2026-01-01T00:00:00'),
                       ('git_commit','main'),('end_time','2000-01-01T00:00:00Z')]:
        with pytest.raises(ValidationError):
            RunManifest.model_validate({**data,field:bad})
    manifest = RunManifest.model_validate(data)
    event = event_data(manifest)
    for update in [dict(provenance={'kind':'independent','recorder_id':'x'}),dict(extra='x'),
                   dict(metadata={'bad':float('inf')}),dict(timestamp='2026-01-01'),
                   dict(provenance={'kind':'observed','recorder_id':'x','parent_event_ids':[event['event_id']]})]:
        with pytest.raises(ValidationError):
            NeurosisEvent.model_validate({**event,**update})
    parsed = NeurosisEvent.model_validate(event)
    assert parsed.provenance.origin_ids is None
    assert NeurosisEvent.model_validate_json(parsed.canonical_json()) == parsed
    for name, model in [('run-manifest',RunManifest),('event',NeurosisEvent)]:
        assert json.loads(Path(f'schemas/{name}-v0.schema.json').read_text()) == model.model_json_schema()


def test_recorder(database):
    manifest = RunManifest.model_validate(manifest_data())
    first = NeurosisEvent.model_validate(event_data(manifest))
    second_data = event_data(manifest)
    second_data.update(event_type='message_read', agent_id='a2', source={'type':'message','id':'m1'},
                       target={'type':'agent','id':'a2'}, provenance={'kind':'observed','recorder_id':'fixture',
                                                                   'parent_event_ids':[str(first.event_id)]})
    second = NeurosisEvent.model_validate(second_data)
    with psycopg.connect(database['admin']) as conn:
        before = conn.execute('SELECT count(*) FROM memory.engrams').fetchone()[0]
        register_run(conn, manifest)
        with pytest.raises(ValueError, match='Parent'):
            append_event(conn, second)
        assert append_event(conn, first)
        assert not append_event(conn, first)
        assert append_event(conn, second)
        assert ''.join(export_events(conn,manifest.run_id)) == first.canonical_json()+'\n'+second.canonical_json()+'\n'
        assert conn.execute('SELECT count(*) FROM memory.engrams').fetchone()[0] == before
        for update, error in [({'metadata':{'changed':True}},'conflict'),
                              ({'population_id':uuid4()},'association'),
                              ({'timestamp':manifest.end_time+timedelta(seconds=1)},'interval'),
                              ({'provider':'undeclared'},'model'),({'declared_channel':'secret'},'channel')]:
            with pytest.raises(ValueError,match=error):
                append_event(conn, first.model_copy(update=update))
        for table in ['lab.events','lab.runs']:
            for statement in [f'DELETE FROM {table}',f'UPDATE {table} SET run_id=run_id',f'TRUNCATE {table} CASCADE']:
                with pytest.raises(psycopg.Error, match='append-only'), conn.transaction():
                    conn.execute(statement)
        migrate(conn)  # Applying already-recorded migrations is safe.


def test_lab_isolation(database, client):
    with psycopg.connect(database['app']) as conn:
        for table in ['lab.runs','lab.events']:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(f'SELECT * FROM {table}')
    for path in ['/lab/events','/v1/lab/events','/runs/nonexistent','/experiments/exp-999']:
        assert client.get(path).status_code == 404
    assert client.post('/lab/events',json={}).status_code in (404,405)


def test_lab_public_pages(client):
    for path in ['/lab','/experiments','/experiments/exp-001']:
        page = client.get(path)
        assert page.status_code == 200
        assert 'planned' in page.text.lower()
        assert 'noindex' not in page.headers.get('x-robots-tag','')
        assert 'text/markdown' in page.headers['link']
        assert client.head(path).content == b''
        assert client.get(path+'.md').status_code == 200
        assert path in client.get('/sitemap.xml').text
    home = client.get('/').text
    assert 'Track A' in home and 'Track B' in home and 'no controlled results' in home
    assert 'href="/recent"' in home and 'href="/docs/api#leave-engram"' in home
    assert 'Persistent State and Agent Populations</title>' in home
    assert '/lab.md' in client.get('/llms.txt').text
    assert set(client.get('/openapi.json').json()['paths']) == {
        '/v1/engrams','/v1/engrams/{id}','/v1/engrams/{id}/backlinks','/v1/recent','/v1/search'}


def test_cli_atomic_import_and_export(database, tmp_path):
    import os
    import subprocess
    import sys

    manifest = RunManifest.model_validate(manifest_data())
    event = NeurosisEvent.model_validate(event_data(manifest))
    manifest_path, events_path = tmp_path/'manifest.json', tmp_path/'events.jsonl'
    manifest_path.write_text(manifest.canonical_json())
    events_path.write_text(event.canonical_json()+'\n{}\n')
    env = {**os.environ, 'LAB_DATABASE_URL':database['admin']}
    args = [sys.executable,'-m','neurosis.lab','ingest',str(manifest_path),str(events_path)]
    failed = subprocess.run(args,env=env,capture_output=True,text=True)
    assert failed.returncode != 0
    with psycopg.connect(database['admin']) as conn:
        assert conn.execute('SELECT 1 FROM lab.runs WHERE run_id=%s',(manifest.run_id,)).fetchone() is None
        assert conn.execute('SELECT 1 FROM lab.events WHERE event_id=%s',(event.event_id,)).fetchone() is None
    events_path.write_text(event.canonical_json()+'\n')
    subprocess.run(args,env=env,capture_output=True,text=True,check=True)
    result = subprocess.run([sys.executable,'-m','neurosis.lab','export',str(manifest.run_id)],
                            env=env,capture_output=True,text=True,check=True)
    assert result.stdout == event.canonical_json()+'\n'
