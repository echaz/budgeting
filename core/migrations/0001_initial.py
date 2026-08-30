import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("institution", models.CharField(max_length=100)),
                ("account_type", models.CharField(
                    choices=[
                        ("credit_card", "Credit card"),
                        ("savings", "Savings"),
                        ("amazon", "Amazon"),
                    ],
                    max_length=20,
                )),
                ("nickname", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["institution", "nickname"],
            },
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "ordering": ["name"],
                "verbose_name_plural": "categories",
            },
        ),
        migrations.CreateModel(
            name="Domain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("description", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions", to="core.account")),
                ("category", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions", to="core.category")),
                ("domain", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions", to="core.domain")),
            ],
            options={
                "ordering": ["-date", "-created_at"],
            },
        ),
    ]
