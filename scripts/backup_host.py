"""Standalone host database backup -- dumps Postgres without booting Django.

The host virtualenv does not carry django_extensions, so `manage.py backup`
cannot import settings here. This script talks to Postgres directly with
pg_dump and reproduces the two-slot rotation, gzip integrity check and growth
check of core/management/commands/backup.py.

Run it on the docker host (the db service is published on localhost:5433):

    python scripts/backup_host.py [--force]

Connection settings come from the environment (loaded from .env when present):
POSTGRES_DB, POSTGRES_USER, PS_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
BACKUP_DIR. Host defaults point at localhost:5433.
"""
import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FILE1_NAME = "backup_file1.sql.gz"
FILE2_NAME = "backup_file2.sql.gz"


def fail(message):
    sys.stderr.write(f"error: {message}\n")
    raise SystemExit(1)


def load_env(path):
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def db_config():
    return {
        "NAME": os.environ.get("POSTGRES_DB", "budgeting"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("PS_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
    }


def uncompressed_size(path):
    total = 0
    with gzip.open(path, "rb") as gz:
        while True:
            chunk = gz.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
    return total


def dump_and_gzip(backup_dir, db, via_docker):
    if via_docker:
        cmd = [
            "docker", "compose", "exec", "-T", "db",
            "pg_dump",
            "-U", str(db["USER"]),
            "-d", str(db["NAME"]),
            "--no-owner",
            "--no-privileges",
        ]
    else:
        cmd = [
            "pg_dump",
            "-h", str(db["HOST"]),
            "-p", str(db["PORT"]),
            "-U", str(db["USER"]),
            "-d", str(db["NAME"]),
            "--no-owner",
            "--no-privileges",
        ]
    env = {**os.environ, "PGPASSWORD": str(db["PASSWORD"])}

    fd, tmp_name = tempfile.mkstemp(suffix=".sql.gz", dir=backup_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=BASE_DIR
    )
    try:
        with gzip.open(tmp_path, "wb") as gz:
            shutil.copyfileobj(proc.stdout, gz)
    finally:
        proc.stdout.close()
    _, stderr = proc.communicate()

    if proc.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        fail(f"pg_dump failed (exit {proc.returncode}): {stderr.decode(errors='replace').strip()}")

    return tmp_path


def verify_gzip(path):
    if path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        fail("dump produced an empty file, aborting.")
    try:
        return uncompressed_size(path)
    except OSError as exc:
        path.unlink(missing_ok=True)
        fail(f"dump failed gzip integrity check, aborting: {exc}")


def check_growth(previous, tmp_path, new_uncompressed):
    try:
        old_uncompressed = uncompressed_size(previous)
    except OSError:
        sys.stderr.write(
            f"warning: could not read previous backup {previous} to compare sizes; "
            "skipping growth check.\n"
        )
        return
    if new_uncompressed <= old_uncompressed:
        tmp_path.unlink(missing_ok=True)
        fail(
            f"new backup ({new_uncompressed} bytes uncompressed) is not larger than the "
            f"previous backup ({old_uncompressed} bytes uncompressed); aborting without rotating."
        )


def main():
    parser = argparse.ArgumentParser(description="Dump Postgres on the host into the rotating buffer.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the check that the new backup is larger than the previous one.",
    )
    args = parser.parse_args()

    load_env(BASE_DIR / ".env")
    db = db_config()

    backup_dir = Path(os.environ.get("BACKUP_DIR", BASE_DIR / "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    file1 = backup_dir / FILE1_NAME
    file2 = backup_dir / FILE2_NAME

    tmp_path = dump_and_gzip(backup_dir, db)
    new_uncompressed = verify_gzip(tmp_path)

    if file1.exists():
        if not args.force:
            check_growth(file1, tmp_path, new_uncompressed)
        os.replace(file1, file2)
    os.replace(tmp_path, file1)

    print(f"Backup complete: {file1} ({file1.stat().st_size} bytes)")
    if file2.exists():
        print(f"Previous backup rotated to: {file2} ({file2.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
