from django.db import models


class Account(models.Model):
    class AccountType(models.TextChoices):
        CREDIT_CARD = "credit_card", "Credit card"
        SAVINGS = "savings", "Savings"
        AMAZON = "amazon", "Amazon"

    institution = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    nickname = models.CharField(max_length=100)
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


class Transaction(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="transactions"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="transactions"
    )
    domain = models.ForeignKey(
        Domain, on_delete=models.PROTECT, related_name="transactions"
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} {self.description} {self.amount}"
