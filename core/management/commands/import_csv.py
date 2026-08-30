from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Account, ImportFile
from scrapers.chase import ChaseImporter
from scrapers.citi import CitiImporter
from scrapers.santander import SantanderImporter

SOURCES = {
    "citi": CitiImporter,
    "santander": SantanderImporter,
    "chase": ChaseImporter,
}


class Command(BaseCommand):
    help = "Crawl an Account's statements directory and import every CSV, idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--account",
            required=True,
            help="Nickname of the Account whose statements_dir to crawl.",
        )
        parser.add_argument(
            "--source",
            required=True,
            choices=sorted(SOURCES),
            help="Which parser to use for the files in the directory.",
        )

    def handle(self, *args, **options):
        account = self._resolve_account(options["account"])
        directory = self._resolve_directory(account)
        importer_class = SOURCES[options["source"]]

        files = sorted(
            p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() == ".csv"
        )
        if not files:
            raise CommandError(f"No CSV files found in {directory}")

        total = 0
        skipped = 0
        for path in files:
            if ImportFile.objects.filter(
                account=account, filename=path.name, completed=True
            ).exists():
                skipped += 1
                self.stdout.write(f"{path.name}: skipped (already imported)")
                continue

            import_file = importer_class(account, str(path)).run()
            total += import_file.row_count
            self.stdout.write(
                f"{path.name}: {import_file.row_count} imported "
                f"({import_file.transaction_start_date} to {import_file.transaction_end_date})"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Done. {total} transactions imported into '{account.nickname}' from "
            f"{len(files)} file(s), {skipped} skipped."
        ))

    def _resolve_account(self, nickname):
        try:
            return Account.objects.get(nickname=nickname)
        except Account.DoesNotExist:
            raise CommandError(f"No Account with nickname {nickname!r}.")
        except Account.MultipleObjectsReturned:
            raise CommandError(f"Multiple Accounts share the nickname {nickname!r}; disambiguate them.")

    def _resolve_directory(self, account):
        if not account.statements_dir:
            raise CommandError(f"Account '{account.nickname}' has no statements_dir set.")
        directory = Path(account.statements_dir)
        if not directory.is_absolute():
            directory = settings.BASE_DIR / directory
        if not directory.is_dir():
            raise CommandError(f"Directory not found: {directory}")
        return directory
