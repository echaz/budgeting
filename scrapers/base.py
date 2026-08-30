import csv
import os

from core.models import ImportFile


class BaseCsvImporter:
    def __init__(self, account, filename):
        self.account = account
        self.filename = filename

    def createTransaction(self, row, import_file):
        raise NotImplementedError(
            f"{type(self).__name__} must implement createTransaction()"
        )

    def open_rows(self):
        with open(self.filename, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                yield row

    def run(self):
        import_file = ImportFile.objects.create(
            account=self.account,
            filename=os.path.basename(self.filename),
        )

        created = []
        for row in self.open_rows():
            transaction = self.createTransaction(row, import_file)
            if transaction is not None:
                created.append(transaction)

        dates = [t.date for t in created]
        import_file.row_count = len(created)
        import_file.transaction_start_date = min(dates) if dates else None
        import_file.transaction_end_date = max(dates) if dates else None
        import_file.completed = True
        import_file.save(
            update_fields=[
                "row_count",
                "transaction_start_date",
                "transaction_end_date",
                "completed",
            ]
        )

        return import_file
