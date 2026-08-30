from django.core.management.base import BaseCommand

from core.models import Category, CategoryRule

RULES = [
    (10, r"ONLINE PAYMENT|PAYMENT,? THANK YOU|CARD ONLINE PAYMENT|AUTOPAY", "Card Payment"),
    (10, r"CASH WITHDRAWAL|\bATM\b", "Cash"),
    (10, r"PAYROLL|DIRECT DEP", "Income"),
    (10, r"^CHECK\b", "Check"),
    (20, r"EZ ?-?PASS|EZPASS", "Tolls & Transit"),
    (30, r"WEGMANS|WHOLE ?FDS|WHOLE FOODS|TRADER JOE|COSTCO WHSE|\bALDI\b|ACME|SHOP ?RITE", "Groceries"),
    (30, r"COSTCO GAS|\bWAWA\b|SUNOCO|\bSHELL\b|EXXON|LUKOIL|QUIKTRIP", "Gas"),
    (30, r"STARBUCKS|DUNKIN|\bCOFFEE\b|ULTIMO", "Coffee & Cafes"),
    (30, r"\bCVS\b|WALGREENS|RITE ?AID|PHARMACY", "Pharmacy"),
    (30, r"PHYSICAL THERAPY|BEHAVIOR|\bPHR\*|DENTAL|PEDIATRIC", "Health"),
    (30, r"HOME DEPOT|LOWE'?S|GARDEN CENTER|FLAGG|ACE HARDWARE", "Home & Garden"),
    (30, r"NETFLIX|SPOTIFY|HULU|DISNEY|YOUTUBE|YOUTU", "Streaming"),
    (30, r"OPENAI|CHATGPT|\bICLOUD\b|MICROSOFT|ADOBE|GOOGLE STORAGE", "Software & Subscriptions"),
    (30, r"AMAZON|\bAMZN\b", "Amazon & Shopping"),
    (30, r"INQUIRER|INQUI|NYTIMES|NEW YORK TIMES", "News & Media"),
    (40, r"JERSEY WAHOOS|TOCA BOCA|BUBBELICIOUS|GYMNAST|SOCCER", "Kids & Activities"),
    (90, r"PAYPAL.*XFER|PAYPAL INST", "Transfers"),
    (95, r"PAYPAL", "PayPal (misc)"),
]


class Command(BaseCommand):
    help = "Seed a starter set of CategoryRules (creating their categories)."

    def handle(self, *args, **options):
        categories = 0
        rules = 0
        for priority, pattern, category_name in RULES:
            category, made = Category.objects.get_or_create(name=category_name)
            categories += made
            _, made = CategoryRule.objects.get_or_create(
                pattern=pattern,
                defaults={"category": category, "priority": priority},
            )
            rules += made

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {rules} new rule(s) and {categories} new categor(y/ies). "
            f"Total rules: {CategoryRule.objects.count()}."
        ))
