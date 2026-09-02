from django.contrib import admin

from core.models import Account, Category, CategoryRule, Domain, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "nickname", "institution", "account_type", "is_active")
    list_filter = ("account_type", "institution", "is_active")
    search_fields = ("nickname", "institution")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "exclude_from_reports")
    list_filter = ("exclude_from_reports",)
    search_fields = ("name",)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "priority", "pattern", "min_amount", "max_amount", "category", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("pattern", "note")
    ordering = ("priority", "id")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "description", "amount", "account", "category", "domain")
    list_filter = ("category", "domain", "account")
    search_fields = ("description",)
    date_hierarchy = "date"
