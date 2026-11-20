from django.contrib import admin

from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "description", "amount", "payment_method", "created_by")
    list_filter = ("category", "payment_method")
    search_fields = ("description", "payee", "reference")
    date_hierarchy = "date"
