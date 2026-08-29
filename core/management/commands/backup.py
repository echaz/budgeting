import gzip
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

FILE1_NAME = "backup_file1.sql.gz"
FILE2_NAME = "backup_file2.sql.gz"


class Command(BaseCommand):
    help = "Dump the Postgres database and rotate it through a two-slot backup buffer."

    def handle(self, *args, **options):
        self._check_database_healthy()

        backup_dir = Path(getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        file1 = backup_dir / FILE1_NAME
        file2 = backup_dir / FILE2_NAME

        tmp_path = self._dump_and_gzip(backup_dir)
        self._verify_gzip(tmp_path)

        if file1.exists():
            os.replace(file1, file2)
        os.replace(tmp_path, file1)

        self.stdout.write(self.style.SUCCESS(
            f"Backup complete: {file1} ({file1.stat().st_size} bytes)"
        ))
        if file2.exists():
            self.stdout.write(
                f"Previous backup rotated to: {file2} ({file2.stat().st_size} bytes)"
            )

    def _check_database_healthy(self):
        conn = connections["default"]
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.execute("SELECT pg_is_in_recovery()")
                in_recovery = cursor.fetchone()[0]
        except OperationalError as exc:
            raise CommandError(f"Database is down or unreachable, aborting backup: {exc}")

        if in_recovery:
            raise CommandError("Database is in recovery mode, aborting backup.")

    def _dump_and_gzip(self, backup_dir):
        db = settings.DATABASES["default"]
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

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            with gzip.open(tmp_path, "wb") as gz:
                shutil.copyfileobj(proc.stdout, gz)
        finally:
            proc.stdout.close()
        _, stderr = proc.communicate()

        if proc.returncode != 0:
            tmp_path.unlink(missing_ok=True)
            raise CommandError(
                f"pg_dump failed (exit {proc.returncode}): "
                f"{stderr.decode(errors='replace').strip()}"
            )

        return tmp_path

    def _verify_gzip(self, path):
        if path.stat().st_size == 0:
            path.unlink(missing_ok=True)
            raise CommandError("Dump produced an empty file, aborting.")
        try:
            with gzip.open(path, "rb") as gz:
                while gz.read(1024 * 1024):
                    pass
        except OSError as exc:
            path.unlink(missing_ok=True)
            raise CommandError(f"Dump failed gzip integrity check, aborting: {exc}")
