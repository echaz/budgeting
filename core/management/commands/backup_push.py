import hashlib
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.gdrive import DriveBackupStore, DriveConfigError

FILE1_NAME = "backup_file1.sql.gz"


class Command(BaseCommand):
    help = "Push the newest local backup to the double-buffered Google Drive store."

    def handle(self, *args, **options):
        local = Path(getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "backups")) / FILE1_NAME
        if not local.exists() or local.stat().st_size == 0:
            raise CommandError(f"No local backup to push at {local}. Run `backup` first.")

        try:
            store = DriveBackupStore(
                client_id=settings.GDRIVE_CLIENT_ID,
                client_secret=settings.GDRIVE_CLIENT_SECRET,
                refresh_token=settings.GDRIVE_REFRESH_TOKEN,
                folder_id=settings.GDRIVE_FOLDER_ID,
            )
        except DriveConfigError as exc:
            raise CommandError(str(exc))

        md5 = self._md5(local)
        size = local.stat().st_size

        folder_id = store.ensure_folder()
        current = store.read_manifest().get("current")
        target = "b" if current == "a" else "a"

        self.stdout.write(f"Uploading {local.name} ({size} bytes) to slot '{target}'...")
        meta = store.upload_to_slot(target, str(local))

        remote_md5 = meta.get("md5Checksum")
        remote_size = int(meta.get("size", 0))
        if remote_md5 != md5 or remote_size != size:
            raise CommandError(
                "Upload verification failed "
                f"(local md5={md5} size={size}, remote md5={remote_md5} size={remote_size}); "
                "manifest not flipped."
            )

        store.write_manifest({
            "current": target,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "md5": md5,
            "size": size,
            "slot_file_id": meta.get("id"),
            "source": local.name,
        })

        self.stdout.write(self.style.SUCCESS(
            f"Pushed to Drive slot '{target}' and flipped manifest "
            f"(previous current was '{current}'). Folder id: {folder_id}"
        ))

    def _md5(self, path):
        digest = hashlib.md5()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
