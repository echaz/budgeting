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
