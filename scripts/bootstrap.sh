#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID == 0 ]] || { echo 'Run with sudo: installs dedicated system services.' >&2; exit 1; }
[[ -f .env ]] || { echo 'Copy .env.example to .env and configure it first.' >&2; exit 1; }
apt-get update
apt-get install -y python3-venv postgresql postgresql-client curl rsync
# A dedicated Internet VPS has no need for multicast hostname discovery.
if systemctl is-active --quiet systemd-resolved; then
    install -d -m 0755 /etc/systemd/resolved.conf.d
    install -m 0644 deploy/resolved-neurosis.conf /etc/systemd/resolved.conf.d/neurosis.conf
    systemctl restart systemd-resolved
fi
pg_bin=$(pg_config --bindir)
getent group neurosis-ingress >/dev/null || groupadd --system neurosis-ingress
id neurosis-api >/dev/null 2>&1 || useradd --system --gid neurosis-ingress --home-dir /nonexistent --shell /usr/sbin/nologin neurosis-api
getent group neurosis-tunnel >/dev/null || groupadd --system neurosis-tunnel
id neurosis-tunnel >/dev/null 2>&1 || useradd --system --gid neurosis-tunnel --home-dir /nonexistent --shell /usr/sbin/nologin neurosis-tunnel
usermod -a -G neurosis-ingress,neurosis-tunnel neurosis-tunnel
install -d -o root -g neurosis-tunnel -m 0750 /etc/neurosis-tunnel
install -d -m 0755 /opt/neurosis-app /etc/neurosis
rsync -a --delete --exclude='__pycache__' neurosis migrations public scripts deploy /opt/neurosis-app/
install -m 0644 requirements.lock /opt/neurosis-app/requirements.lock
chown -R root:root /opt/neurosis-app
python3 -m venv /opt/neurosis-app/.venv
/opt/neurosis-app/.venv/bin/pip install --require-hashes -r /opt/neurosis-app/requirements.lock
install -m 0600 .env /etc/neurosis/api.env.new
# Correct the production Unix peer DSN; never shell-source the environment file.
python3 - <<'PY'
from pathlib import Path
import re, secrets
p=Path('/etc/neurosis/api.env')
previous=p.read_text() if p.exists() else ''
s=Path('/etc/neurosis/api.env.new').read_text()
s=re.sub(r'^DATABASE_URL=.*$', 'DATABASE_URL="dbname=neurosis user=neurosis-api host=/run/postgresql-neurosis port=5433"', s, flags=re.M)
if 'REPLACE_WITH_64_RANDOM_HEX_CHARACTERS' in s:
    old=re.search(r'^TELEMETRY_KEY=([a-f0-9]{64})$',previous,re.M)
    s=s.replace('REPLACE_WITH_64_RANDOM_HEX_CHARACTERS',old[1] if old else secrets.token_hex(32))
p.write_text(s)
p.chmod(0o600)
Path('/etc/neurosis/api.env.new').unlink()
retention=re.search(r'^TELEMETRY_RETENTION_DAYS=(\d+)$',s,re.M)
Path('/etc/neurosis/retention.env').write_text('DATABASE_URL="dbname=neurosis user=postgres host=/run/postgresql-neurosis port=5433"\nTELEMETRY_RETENTION_DAYS='+ (retention[1] if retention else '14')+'\n')
PY
install -m 0644 deploy/postgresql.conf deploy/pg_hba.conf /etc/neurosis/
install -d -o postgres -g postgres -m 0700 /var/lib/postgresql/neurosis
if [[ ! -f /var/lib/postgresql/neurosis/PG_VERSION ]]; then
    runuser -u postgres -- "$pg_bin/initdb" -D /var/lib/postgresql/neurosis --encoding=UTF8 --locale=C.UTF-8 --auth-local=peer --auth-host=scram-sha-256 >/dev/null
fi
[[ $(cat /var/lib/postgresql/neurosis/PG_VERSION) == $("$pg_bin/postgres" --version | awk '{print $3}' | cut -d. -f1) ]] || { echo 'PostgreSQL major version mismatch; perform a documented pg_upgrade or restore.' >&2; exit 1; }
sed "s|@PG_BIN@|$pg_bin|g" deploy/neurosis-postgresql.service > /etc/systemd/system/neurosis-postgresql.service
install -m 0644 deploy/neurosis-api.service deploy/neurosis-retention.service deploy/neurosis-retention.timer /etc/systemd/system/
install -m 0644 scripts/network_probe.py /usr/local/lib/neurosis-network-probe.py
systemctl daemon-reload
systemctl enable --now neurosis-postgresql.service
for attempt in $(seq 1 30); do
    runuser -u postgres -- psql -h /run/postgresql-neurosis -p 5433 -d postgres -Atqc 'SELECT 1' >/dev/null 2>&1 && break
    sleep 1
done
runuser -u postgres -- psql -h /run/postgresql-neurosis -p 5433 -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE ROLE "neurosis-api" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='neurosis-api') \gexec
SELECT 'CREATE DATABASE neurosis' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='neurosis') \gexec
REVOKE ALL ON DATABASE neurosis FROM PUBLIC;
GRANT CONNECT ON DATABASE neurosis TO "neurosis-api";
SQL
cd /opt/neurosis-app
runuser -u postgres -- env DATABASE_URL='dbname=neurosis user=postgres host=/run/postgresql-neurosis port=5433' .venv/bin/python -m neurosis.admin migrate
runuser -u postgres -- psql -h /run/postgresql-neurosis -p 5433 -d neurosis -v ON_ERROR_STOP=1 <<'SQL'
GRANT USAGE ON SCHEMA memory,research TO "neurosis-api";
GRANT SELECT ON memory.engrams,memory.engram_references TO "neurosis-api";
GRANT INSERT(id,content,sha256,parent_id) ON memory.engrams TO "neurosis-api";
-- FOR SHARE requires an UPDATE privilege. Grant only the unchangeable ID;
-- the immutable trigger rejects any actual change, and the API has no UPDATE route.
GRANT UPDATE(id) ON memory.engrams TO "neurosis-api";
GRANT INSERT(source_id,target_id) ON memory.engram_references TO "neurosis-api";
GRANT INSERT ON research.requests TO "neurosis-api";
ALTER ROLE "neurosis-api" SET statement_timeout='1500ms';
ALTER ROLE "neurosis-api" SET idle_in_transaction_session_timeout='5s';
SQL
systemctl enable neurosis-api.service neurosis-retention.timer
systemctl restart neurosis-api.service
systemctl start neurosis-retention.timer
install -d -m 0700 /var/backups/neurosis
install -m 0644 deploy/neurosis-backup.service deploy/neurosis-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now neurosis-backup.timer
echo 'API and isolated PostgreSQL installed. Configure the existing tunnel, then run scripts/start.sh. Public ingress has not been started by this script.'
