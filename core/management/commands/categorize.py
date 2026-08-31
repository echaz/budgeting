import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from core.models import CategoryRule, Transaction


class Command(BaseCommand):
    help = "Apply CategoryRule regexes to transaction descriptions to set their category."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-apply rules to every transaction, overwriting existing categories on a match.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--show-unmatched",
            type=int,
            default=25,
            metavar="N",
            help="How many top still-uncategorized descriptions to list (default 25).",
        )

    def handle(self, *args, **options):
        rules = self._load_rules()
        if not rules:
            raise CommandError("No active CategoryRules. Seed some first (see seed_category_rules).")

        queryset = Transaction.objects.all()
        if not options["all"]:
            queryset = queryset.filter(category__isnull=True)

        updates = []
        matched = 0
        considered = 0
        for tx in queryset.only("id", "description", "amount", "category").iterator():
            considered += 1
            category = self._first_match(rules, tx.description, tx.amount)
            if category is None:
                continue
            if tx.category_id != category.id:
                tx.category = category
                updates.append(tx)
            matched += 1

        if not options["dry_run"] and updates:
            Transaction.objects.bulk_update(updates, ["category"], batch_size=500)

        verb = "would categorize" if options["dry_run"] else "categorized"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {matched} of {considered} considered "
            f"({len(updates)} changed)."
        ))
        self._report_unmatched(options["show_unmatched"])

    def _load_rules(self):
        rules = list(CategoryRule.objects.filter(is_active=True).select_related("category"))
        for rule in rules:
            try:
                re.compile(rule.pattern)
            except re.error as exc:
                raise CommandError(f"Bad regex in rule {rule.id} ({rule.pattern!r}): {exc}")
        return rules

    def _first_match(self, rules, description, amount):
        for rule in rules:
            if rule.matches(description, amount):
                return rule.category
        return None

    def _report_unmatched(self, limit):
        if limit <= 0:
            return
        counter = Counter()
        remaining = Transaction.objects.filter(category__isnull=True)
        for description in remaining.values_list("description", flat=True):
            key = re.sub(r"\s+", " ", re.sub(r"[0-9]+", " ", description)).strip().upper()[:40]
            counter[key] += 1
        total = remaining.count()
        if not total:
            self.stdout.write("All transactions are categorized.")
            return
        self.stdout.write(f"\n{total} still uncategorized. Top {limit} patterns:")
        for key, count in counter.most_common(limit):
            self.stdout.write(f"  {count:5}  {key}")
