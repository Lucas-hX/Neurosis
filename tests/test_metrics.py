from neurosis.metrics import Metrics


def test_metrics_counts_successful_activity_without_exposing_visitors(client):
    before = client.get('/metrics.json').json()['since_start']
    response = client.post('/v1/engrams', json={'content': 'private-marker-for-metrics-test'},
                           headers={'User-Agent': 'private-user-agent-marker'})
    assert response.status_code == 201
    id = response.json()['id']
    assert client.get('/v1/engrams/' + id).status_code == 200
    assert client.get('/v1/search?q=private-marker-for-metrics-test').status_code == 200
    assert client.get('/v1/recent').status_code == 200
    assert client.get('/v1/engrams/' + id + '/backlinks').status_code == 200
    assert client.post('/v1/engrams', json={'content': ''}).status_code == 400
    response = client.get('/metrics.json')
    after = response.json()['since_start']
    assert after['engrams_written'] == before['engrams_written'] + 1
    assert after['engram_reads'] == before['engram_reads'] + 1
    assert after['searches'] == before['searches'] + 1
    assert after['client_errors'] == before['client_errors'] + 1
    assert after['recent_reads'] == before['recent_reads'] + 1
    assert after['backlink_reads'] == before['backlink_reads'] + 1
    assert after['requests'] == before['requests'] + 6
    for secret in (id, 'private-marker', 'private-user-agent', 'cluster', 'cf_ray'):
        assert secret not in response.text
    assert 'noindex' in response.headers['x-robots-tag']
    assert 'no-store' in response.headers['cache-control']
    assert client.get('/healthz').status_code == 200
    page = client.get('/metrics')
    assert page.status_code == 200 and '<table>' in page.text
    assert '<script' not in page.text
    assert client.head('/metrics').content == b''
    assert client.get('/metrics.json').json()['since_start'] == after


def test_metrics_window_expires_and_storage_is_bounded(monkeypatch):
    clock = [0]
    monkeypatch.setattr('neurosis.metrics.time.monotonic', lambda: clock[0])
    metrics = Metrics()
    event = dict(request_bytes=0, response_bytes=20, latency_ms=3, status=429, events=[])
    for minute in range(100):
        clock[0] = minute * 60
        metrics.observe(event)
    snapshot = metrics.snapshot()
    assert len(metrics.minutes) == 60
    assert snapshot['since_start']['rate_limited'] == 100
    assert snapshot['recent']['rate_limited'] == 5
    clock[0] += 300
    assert metrics.snapshot()['recent']['requests'] == 0
    assert Metrics().snapshot()['since_start']['requests'] == 0
