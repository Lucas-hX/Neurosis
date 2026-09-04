#!/bin/bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
backup_dir=${1:-/var/backups/neurosis}
install -d -m 0700 "$backup_dir"
umask 077
backup_file="$backup_dir/$(date -u +%Y%m%dT%H%M%SZ).dump"
# Consistent online snapshot, data and schemas; roles recreated by bootstrap.
runuser -u postgres -- pg_dump -h /run/postgresql-neurosis -p 5433 -d neurosis --format=custom --no-owner > "$backup_file.tmp"
pg_restore --list "$backup_file.tmp" >/dev/null
mv "$backup_file.tmp" "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
# Expire only snapshots with this script's exact generated naming convention.
python3 - "$backup_dir" <<'PYCODE'
import os,re,sys,time
from pathlib import Path
days=int(os.getenv('BACKUP_RETENTION_DAYS','14'))
if days<1:
    raise SystemExit('BACKUP_RETENTION_DAYS must be positive')
for path in Path(sys.argv[1]).glob('*.dump'):
    if re.fullmatch(r'\d{8}T\d{6}Z\.dump',path.name) and path.stat().st_mtime < time.time()-days*86400:
        path.unlink()
        path.with_name(path.name+'.sha256').unlink(missing_ok=True)
PYCODE
echo "$backup_file"
