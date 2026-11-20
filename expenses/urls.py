from django.urls import path

from . import views

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("new/", views.expense_form, name="expense_create"),
    path("<int:pk>/edit/", views.expense_form, name="expense_edit"),
    path("<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("categories/", views.category_list, name="expense_category_list"),
    path("categories/<int:pk>/toggle/", views.category_toggle, name="expense_category_toggle"),
    path("export.csv", views.expense_csv, name="expense_csv"),
]
