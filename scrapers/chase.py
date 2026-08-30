from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from core.models import Transaction
from scrapers.base import BaseCsvImporter


class ChaseImporter(BaseCsvImporter):
    def __init__(self, account, filename):
        super().__init__(account, filename)
        self._db_counts = {}
        self._seen = defaultdict(int)

    def parse_decimal(self, value):
        value = (value or "").strip().replace(",", "").replace("$", "").replace("+", "")
        return Decimal(value) if value else Decimal("0")

    def parse_date(self, value):
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()

    def createTransaction(self, row, import_file):
        date = self.parse_date(row["Transaction Date"])
        amount = -self.parse_decimal(row.get("Amount"))
        description = row["Description"].strip()[:255]

        key = (date, amount, description)
        if key not in self._db_counts:
            self._db_counts[key] = Transaction.objects.filter(
                account=self.account,
                date=date,
                amount=amount,
                description=description,
            ).count()

        occurrence = self._seen[key]
        self._seen[key] += 1
        if occurrence < self._db_counts[key]:
            return None

        return Transaction.objects.create(
            account=self.account,
            category=None,
            domain=None,
            import_file=import_file,
            transaction_number=None,
            date=date,
            amount=amount,
            description=description,
        )
