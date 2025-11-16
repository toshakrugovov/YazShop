from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from main import views

schema_view = get_schema_view(
    openapi.Info(
        title="YazShop API",
        default_version='v1',
        description="API документация",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Кастомные админские пути (должны быть ПЕРЕД admin.site.urls)
    path('admin/users/', views.admin_users_list, name='admin_users_list'),
    path('admin/users/create/', views.admin_user_create, name='admin_user_create'),
    path('admin/users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('admin/users/<int:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),
    path('admin/roles/', views.admin_roles_list, name='admin_roles_list'),
    path('admin/products/', views.admin_products_list, name='admin_products_list'),
    path('admin/products/add/', views.admin_product_add, name='admin_product_add'),
    path('admin/products/<int:product_id>/edit/', views.admin_product_edit, name='admin_product_edit'),
    path('admin/products/<int:product_id>/delete/', views.admin_product_delete, name='admin_product_delete'),
    path('admin/orders/', views.admin_orders_list, name='admin_orders_list'),
    path('admin/orders/<int:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/support/', views.admin_support_list, name='admin_support_list'),
    path('admin/support/<int:ticket_id>/', views.admin_support_detail, name='admin_support_detail'),
    path('admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin/analytics/export.csv', views.admin_analytics_export_csv, name='admin_analytics_export_csv'),
    path('admin/analytics/export.pdf', views.admin_analytics_export_pdf, name='admin_analytics_export_pdf'),
    path('admin/activity-logs/', views.admin_activity_logs, name='admin_activity_logs'),
    path('admin/activity-logs/<int:log_id>/', views.admin_activity_log_detail, name='admin_activity_log_detail'),
    path('admin/promotions/', views.admin_promotions_list, name='admin_promotions_list'),
    path('admin/promotions/add/', views.admin_promotion_add, name='admin_promotion_add'),
    path('admin/promotions/<int:promo_id>/edit/', views.admin_promotion_edit, name='admin_promotion_edit'),
    path('admin/promotions/<int:promo_id>/delete/', views.admin_promotion_delete, name='admin_promotion_delete'),
    path('admin/categories/', views.admin_categories_list, name='admin_categories_list'),
    path('admin/categories/add/', views.admin_category_add, name='admin_category_add'),
    path('admin/categories/<int:category_id>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin/brands/add/', views.admin_brand_add, name='admin_brand_add'),
    path('admin/brands/<int:brand_id>/edit/', views.admin_brand_edit, name='admin_brand_edit'),
    path('admin/suppliers/', views.admin_suppliers_list, name='admin_suppliers_list'),
    path('admin/suppliers/add/', views.admin_supplier_add, name='admin_supplier_add'),
    path('admin/suppliers/<int:supplier_id>/edit/', views.admin_supplier_edit, name='admin_supplier_edit'),
    path('admin/suppliers/<int:supplier_id>/delete/', views.admin_supplier_delete, name='admin_supplier_delete'),
    path('admin/backups/', views.admin_backups_list, name='admin_backups_list'),
    path('admin/backups/create/', views.admin_backup_create, name='admin_backup_create'),
    path('admin/backups/<int:backup_id>/download/', views.admin_backup_download, name='admin_backup_download'),
    path('admin/backups/<int:backup_id>/delete/', views.admin_backup_delete, name='admin_backup_delete'),
    path('admin/org-account/', views.admin_org_account, name='admin_org_account'),
    # Django Admin (после кастомных путей)
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # Catch-all для обработки 404 ошибок (должен быть последним)
    re_path(r'^.*$', views.handler404, name='404'),
]

# Обработчик 404
handler404 = 'main.views.handler404'

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()