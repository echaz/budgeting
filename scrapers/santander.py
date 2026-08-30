import csv
from datetime import datetime
from decimal import Decimal

from core.models import Transaction
from scrapers.base import BaseCsvImporter

DETAIL_MARKER = "Serial Num"


class SantanderImporter(BaseCsvImporter):
    def open_rows(self):
        with open(self.filename, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))

        header = None
        for row in rows:
            if header is None:
                if DETAIL_MARKER in [cell.strip() for cell in row]:
                    header = [cell.strip() for cell in row]
                continue
            if not any(cell.strip() for cell in row):
                continue
            yield dict(zip(header, row))

    def parse_decimal(self, value):
        value = (value or "").strip().replace(",", "").replace("$", "").replace("+", "")
        return Decimal(value) if value else Decimal("0")

    def parse_date(self, value):
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()

    def createTransaction(self, row, import_file):
        serial = (row.get("Serial Num") or "").strip() or None
        if serial is not None and Transaction.objects.filter(
            transaction_number=serial
        ).exists():
            return None

        return Transaction.objects.create(
            account=self.account,
            category=None,
            domain=None,
            import_file=import_file,
            transaction_number=serial,
            date=self.parse_date(row["Date"]),
            amount=-self.parse_decimal(row.get("Amount")),
            description=row.get("Description", "").strip()[:255],
        )
