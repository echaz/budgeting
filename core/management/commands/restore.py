import gzip
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

FILE1_NAME = "backup_file1.sql.gz"
FILE2_NAME = "backup_file2.sql.gz"


class Command(BaseCommand):
    help = "Restore the Postgres database from a local gzipped pg_dump backup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=None,
            help=(
                "Path to a .sql.gz backup. Defaults to the newest slot "
                f"({FILE1_NAME}); pass 'previous' for the prior slot "
                f"({FILE2_NAME}), or an explicit path."
            ),
        )
        parser.add_argument(
            "--noinput", "--no-input",
            action="store_true",
            dest="noinput",
            help="Do not prompt for confirmation before overwriting the database.",
        )

    def handle(self, *args, **options):
        backup_dir = Path(getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups"))
        path = self._resolve_path(backup_dir, options["file"])

        if not path.exists() or path.stat().st_size == 0:
            raise CommandError(f"Backup file not found or empty: {path}")
        self._verify_gzip(path)

        db = settings.DATABASES["default"]

        if not options["noinput"]:
            self.stdout.write(self.style.WARNING(
                f"This will OVERWRITE database '{db['NAME']}' on "
                f"{db['HOST']}:{db['PORT']} with the contents of {path}."
            ))
            if input("Type 'yes' to continue: ").strip().lower() != "yes":
                raise CommandError("Aborted.")

        self._reset_schema(db)
        self._restore(db, path)

        self.stdout.write(self.style.SUCCESS(f"Restore complete from {path}."))

    def _resolve_path(self, backup_dir, file_opt):
        if file_opt in (None, "", "current", "latest"):
            return backup_dir / FILE1_NAME
        if file_opt in ("previous", "prev"):
            return backup_dir / FILE2_NAME
        return Path(file_opt)

    def _verify_gzip(self, path):
        try:
            with gzip.open(path, "rb") as gz:
                while gz.read(1024 * 1024):
                    pass
        except OSError as exc:
            raise CommandError(f"Backup failed gzip integrity check, aborting: {exc}")

    def _psql_base(self, db):
        return [
            "psql",
            "-h", str(db["HOST"]),
            "-p", str(db["PORT"]),
            "-U", str(db["USER"]),
            "-d", str(db["NAME"]),
            "-v", "ON_ERROR_STOP=1",
        ]

    def _reset_schema(self, db):
        cmd = self._psql_base(db) + [
            "-c", "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;",
        ]
        env = {**os.environ, "PGPASSWORD": str(db["PASSWORD"])}
        proc = subprocess.run(cmd, env=env, capture_output=True)
        if proc.returncode != 0:
            raise CommandError(
                "Failed to reset schema: "
                f"{proc.stderr.decode(errors='replace').strip()}"
            )

    def _restore(self, db, path):
        cmd = self._psql_base(db)
        env = {**os.environ, "PGPASSWORD": str(db["PASSWORD"])}
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            with gzip.open(path, "rb") as gz:
                shutil.copyfileobj(gz, proc.stdin)
        finally:
            proc.stdin.close()
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            raise CommandError(
                f"psql restore failed (exit {proc.returncode}): "
                f"{stderr.decode(errors='replace').strip()}"
            )
