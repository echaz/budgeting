"""
URL configuration for budgeting project.
"""
from django.contrib import admin
from django.urls import include, path

from core import views

urlpatterns = [
    path('', views.home, name='home'),
    path('reports/', views.reports_index, name='reports_index'),
    path('reports/categories/', views.category_report, name='category_report'),
    path('reports/compare/', views.category_compare, name='category_compare'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
