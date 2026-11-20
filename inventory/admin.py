from django.contrib import admin

from .models import Ingredient, Purchase, PurchaseItem, StockMovement, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "is_active")
    search_fields = ("name", "phone")


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "stock", "reorder_level", "avg_cost", "supplier", "is_active")
    list_filter = ("is_active", "supplier", "unit")
    search_fields = ("name",)
    # Stock must only change through the ledger (purchases, sales, waste, counts).
    readonly_fields = ("stock",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "ingredient", "kind", "quantity", "balance_after", "reference", "created_by")
    list_filter = ("kind",)
    search_fields = ("ingredient__name", "reference")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("number", "supplier", "status", "created_at", "received_at")
    list_filter = ("status", "supplier")
    inlines = [PurchaseItemInline]
    readonly_fields = ("status", "received_at", "created_by")
