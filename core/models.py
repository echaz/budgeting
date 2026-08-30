from django.db import models


class Account(models.Model):
    class AccountType(models.TextChoices):
        CREDIT_CARD = "credit_card", "Credit card"
        SAVINGS = "savings", "Savings"
        AMAZON = "amazon", "Amazon"

    institution = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    nickname = models.CharField(max_length=100)
    statements_dir = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institution", "nickname"]

    def __str__(self):
        return f"{self.nickname}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Domain(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ImportFile(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="import_files"
    )
    filename = models.CharField(max_length=255)
    row_count = models.PositiveIntegerField(default=0)
    transaction_start_date = models.DateField(null=True, blank=True)
    transaction_end_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.row_count} rows)"


class Transaction(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="transactions"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    import_file = models.ForeignKey(
        ImportFile, on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_number = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} {self.description} {self.amount}"
