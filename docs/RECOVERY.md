# Production recovery for the Railway SQLite deployment

The live service stores its SQLite database at `/app/data/lifeos.db` on the Railway volume. That volume persists service restarts, but it is not a backup. There is no PostgreSQL service in this deployment and this procedure does not rely on one.

`scripts/sqlite_recovery.py` creates a consistent snapshot with SQLite's online backup API. It never copies the live database file, WAL file, or shared-memory file directly. Each snapshot is then encrypted with AES-256-GCM before the archive is retained. The backup key is an operator recovery credential; it must be distinct from `LIFEOS_ENCRYPTION_KEY`, the application's credential.

## One-time operator setup

1. Provision storage outside the Railway volume. Examples are an object-storage bucket reached through a scheduled runner, or a separately mounted encrypted backup volume. It must be mounted in the runner at a path other than `/app/data`; the script refuses `/app/data` and the database directory.
2. Generate a dedicated 32-byte key and store it only in the secret manager used by the backup runner and the restricted restore process:

   ```sh
   python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```

   Set the resulting value as `LIFEOS_BACKUP_KEY`. Do not put it in the application service variables, source control, shell history, or the archive destination.
3. Make the recovery script available to the backup runner with Python 3.11+ and `cryptography` installed. Give the runner read access to `/app/data/lifeos.db`, write access only to its external destination, and the backup key. Railway's normal web-service container has no configured scheduler or external-storage mount, so these are operator prerequisites rather than capabilities provided by the hosted service.

## Scheduled encrypted backup

Run this once per day from the separate runner after mounting its external destination, for example `/backups`. Have the runner's secret manager inject the key, or export it from that manager before invoking the script; never paste the key into the command:

```sh
export LIFEOS_BACKUP_KEY="$(secret-manager read lifeos/backup-key)"
python scripts/sqlite_recovery.py backup \
  --database /app/data/lifeos.db \
  --destination /backups \
  --retention-days 30
```

Replace `secret-manager read lifeos/backup-key` with the command supplied by the provisioned secret manager. The command emits only archive path, checksum, and prune count as JSON. It keeps 30 days of archives named `lifeos-*.sqlite.aesgcm`; use `--retention-days 0` to disable pruning. Configure the runner scheduler and alert on a nonzero exit code or a missing daily JSON result. Copying an encrypted archive to remote object storage is required if `/backups` is merely another local disk; this script intentionally does not claim to configure or manage that provider.

Run a verification job after each upload or at least weekly. It authenticates and decrypts the archive into a temporary file, validates its SHA-256 checksum, and runs SQLite `PRAGMA integrity_check`:

```sh
python scripts/sqlite_recovery.py verify \
  --archive /backups/lifeos-YYYYMMDDTHHMMSSZ.sqlite.aesgcm
```

Verification creates plaintext only in a local private temporary directory, removes it before returning, and never writes it into the archive destination.

## Restore drill and incident restore

Perform a restore drill at least quarterly against a non-production database path. Keep the web service stopped for an actual restore. Restoring while it is running can lose writes or leave open SQLite connections using the prior database.

1. Download the selected encrypted archive from external storage and verify it with the command above.
2. Stop the Railway service and confirm there are no running replicas.
3. Run:

   ```sh
   python scripts/sqlite_recovery.py restore \
     --archive /backups/lifeos-YYYYMMDDTHHMMSSZ.sqlite.aesgcm \
     --database /app/data/lifeos.db
   ```

   The script decrypts to a staging file, verifies authentication, checksum, and SQLite integrity, removes stale `-wal` and `-shm` files, then atomically replaces `lifeos.db`.
4. Start one replica, check `/ready`, authenticate, and validate representative work records. Preserve the incident archive and record the selected archive checksum and restore time in the incident log.

The automated recovery test creates the real `schema_revision` and `documents` schema through `lifeos.store.Database`, backs up an application record, restores it to a new database, and proves both the data and schema survive. It does not access production credentials, Railway volumes, or external storage.
