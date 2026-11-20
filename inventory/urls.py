from django.urls import path

from . import views

urlpatterns = [
    path("", views.ingredient_list, name="ingredient_list"),
    path("new/", views.ingredient_form, name="ingredient_create"),
    path("<int:pk>/edit/", views.ingredient_form, name="ingredient_edit"),
    path("adjust/", views.stock_adjust, name="stock_adjust"),
    path("movements/", views.movement_list, name="movement_list"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/new/", views.supplier_form, name="supplier_create"),
    path("suppliers/<int:pk>/edit/", views.supplier_form, name="supplier_edit"),
    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/new/", views.purchase_form, name="purchase_create"),
    path("purchases/<int:pk>/", views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:pk>/edit/", views.purchase_form, name="purchase_edit"),
    path("purchases/<int:pk>/receive/", views.purchase_receive, name="purchase_receive"),
    path("purchases/<int:pk>/cancel/", views.purchase_cancel, name="purchase_cancel"),
]
