from django.contrib import admin

from core.models import Account, Category, CategoryRule, Domain, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("nickname", "institution", "account_type", "is_active")
    list_filter = ("account_type", "institution", "is_active")
    search_fields = ("nickname", "institution")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    list_display = ("priority", "pattern", "category", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("pattern", "note")
    ordering = ("priority", "id")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "amount", "account", "category", "domain")
    list_filter = ("category", "domain", "account")
    search_fields = ("description",)
    date_hierarchy = "date"
