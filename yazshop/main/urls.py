from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import (
    RoleViewSet, UserProfileViewSet, UserAddressViewSet, CategoryViewSet, BrandViewSet, SupplierViewSet,
    ProductViewSet, ProductSizeViewSet, TagViewSet, ProductTagViewSet, FavoriteViewSet, CartViewSet,
    CartItemViewSet, OrderViewSet, OrderItemViewSet, PaymentViewSet, DeliveryViewSet, PromotionViewSet,
    ProductReviewViewSet, SupportTicketViewSet, ActivityLogViewSet, CheckEmailView, LoginView, RegisterView, ResetPasswordView, VerifyResetDataView,
    ProfileAPIView, AddressAPIView, AddressDetailAPIView, CartAPIView, CartItemAPIView,
    OrderAPIView, OrderDetailAPIView, PaymentMethodAPIView, PaymentMethodDetailAPIView,
    BalanceAPIView, ValidatePromoAPIView,     ProductManagementAPIView, ProductManagementDetailAPIView,
    CategoryManagementAPIView, CategoryManagementDetailAPIView, BrandManagementAPIView,
    BrandManagementDetailAPIView, OrderManagementAPIView, OrderManagementDetailAPIView,
    UserManagementAPIView, UserManagementDetailAPIView, SupportTicketAPIView,
    SupportTicketDetailAPIView, CatalogAPIView, FavoritesAPIView, FavoriteDetailAPIView,
    ProductReviewAPIView, OrganizationAccountAPIView, PromotionManagementAPIView,
    PromotionManagementDetailAPIView, SupplierManagementAPIView, SupplierManagementDetailAPIView,
    RoleManagementAPIView, RoleManagementDetailAPIView, BackupManagementAPIView,
    BackupManagementDetailAPIView
)
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'user-profiles', UserProfileViewSet)
router.register(r'user-addresses', UserAddressViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'brands', BrandViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'products', ProductViewSet)
router.register(r'product-sizes', ProductSizeViewSet)
router.register(r'tags', TagViewSet)
router.register(r'product-tags', ProductTagViewSet)
router.register(r'favorites', FavoriteViewSet)
router.register(r'carts', CartViewSet)
router.register(r'cart-items', CartItemViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'deliveries', DeliveryViewSet)
router.register(r'promotions', PromotionViewSet)
router.register(r'product-reviews', ProductReviewViewSet)
router.register(r'support-tickets', SupportTicketViewSet)
router.register(r'activity-logs', ActivityLogViewSet)

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('contacts/', views.contacts, name='contacts'), 
    path('refund/', views.refund, name='refund'),
    path('bonus/', views.bonus, name='bonus'),
    path('delivery/', views.delivery, name='delivery'), 
    path('favorites/', views.favorites, name='favorites'), 
    path('about/', views.about, name='about'), 
    path('catalog/', views.catalog, name='catalog'),
    
    # Профиль пользователя
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/orders/', views.order_history_view, name='order_history'),
    path('profile/orders/<int:pk>/', views.order_detail_view, name='order_detail'),
    path('profile/addresses/', views.addresses_view, name='addresses'),
    path('profile/payment-methods/', views.payment_methods_view, name='payment_methods'),
    path('profile/payment-methods/add/', views.add_payment_method, name='add_payment_method'),
    path('profile/payment-methods/<int:payment_id>/delete/', views.delete_payment_method, name='delete_payment_method'),
    path('profile/payment-methods/<int:payment_id>/set-default/', views.set_default_payment_method, name='set_default_payment_method'),
    path('profile/payment-methods/<int:card_id>/transactions/', views.get_card_transactions, name='get_card_transactions'),
    path('profile/payment-methods/<int:card_id>/deposit/', views.deposit_from_card, name='deposit_from_card'),
    path('profile/payment-methods/<int:card_id>/withdraw/', views.withdraw_to_card, name='withdraw_to_card'),
    path('profile/payment-methods/<int:card_id>/topup/', views.topup_card_balance, name='topup_card_balance'),

    # Receipts
    path('profile/receipts/', views.receipts_list, name='receipts_list'),
    path('profile/receipts/<int:receipt_id>/pdf/', views.receipt_pdf, name='receipt_pdf'),
    path('profile/notifications/', views.notifications_view, name='notifications'),
    path('profile/balance/', views.balance_view, name='balance'),
    path('profile/balance/deposit/', views.deposit_balance, name='deposit_balance'),
    path('profile/balance/withdraw/', views.withdraw_balance, name='withdraw_balance'),
    path('profile/orders/<int:pk>/cancel/', views.cancel_order, name='cancel_order'),

    # API
    path('api/', include(router.urls)),
    path('api/check-email/', CheckEmailView.as_view(), name='check-email'),
    path('api/login/', LoginView.as_view(), name='api-login'),
    path('api/register/', RegisterView.as_view(), name='api-register'),
    path('api/reset-password/', ResetPasswordView.as_view(), name='api-reset-password'),
    path('api/verify-reset-data/', VerifyResetDataView.as_view(), name='api-verify-reset-data'),
    
    # Новые API endpoints
    path('api/profile/', ProfileAPIView.as_view(), name='api-profile'),
    path('api/addresses/', AddressAPIView.as_view(), name='api-addresses'),
    path('api/addresses/<int:address_id>/', AddressDetailAPIView.as_view(), name='api-address-detail'),
    path('api/cart/', CartAPIView.as_view(), name='api-cart'),
    path('api/cart/items/<int:item_id>/', CartItemAPIView.as_view(), name='api-cart-item'),
    path('api/orders/', OrderAPIView.as_view(), name='api-orders'),
    path('api/orders/<int:order_id>/', OrderDetailAPIView.as_view(), name='api-order-detail'),
    path('api/payment-methods/', PaymentMethodAPIView.as_view(), name='api-payment-methods'),
    path('api/payment-methods/<int:card_id>/', PaymentMethodDetailAPIView.as_view(), name='api-payment-method-detail'),
    path('api/balance/', BalanceAPIView.as_view(), name='api-balance'),
    path('api/validate-promo/', ValidatePromoAPIView.as_view(), name='api-validate-promo'),
    
    # API для менеджеров и админов
    path('api/management/products/', ProductManagementAPIView.as_view(), name='api-management-products'),
    path('api/management/products/<int:product_id>/', ProductManagementDetailAPIView.as_view(), name='api-management-product-detail'),
    path('api/management/categories/', CategoryManagementAPIView.as_view(), name='api-management-categories'),
    path('api/management/categories/<int:category_id>/', CategoryManagementDetailAPIView.as_view(), name='api-management-category-detail'),
    path('api/management/brands/', BrandManagementAPIView.as_view(), name='api-management-brands'),
    path('api/management/brands/<int:brand_id>/', BrandManagementDetailAPIView.as_view(), name='api-management-brand-detail'),
    path('api/management/orders/', OrderManagementAPIView.as_view(), name='api-management-orders'),
    path('api/management/orders/<int:order_id>/', OrderManagementDetailAPIView.as_view(), name='api-management-order-detail'),
    path('api/management/users/', UserManagementAPIView.as_view(), name='api-management-users'),
    path('api/management/users/<int:user_id>/', UserManagementDetailAPIView.as_view(), name='api-management-user-detail'),
    path('api/management/org-account/', OrganizationAccountAPIView.as_view(), name='api-management-org-account'),
    path('api/management/promotions/', PromotionManagementAPIView.as_view(), name='api-management-promotions'),
    path('api/management/promotions/<int:promo_id>/', PromotionManagementDetailAPIView.as_view(), name='api-management-promotion-detail'),
    path('api/management/suppliers/', SupplierManagementAPIView.as_view(), name='api-management-suppliers'),
    path('api/management/suppliers/<int:supplier_id>/', SupplierManagementDetailAPIView.as_view(), name='api-management-supplier-detail'),
    path('api/management/roles/', RoleManagementAPIView.as_view(), name='api-management-roles'),
    path('api/management/roles/<int:role_id>/', RoleManagementDetailAPIView.as_view(), name='api-management-role-detail'),
    path('api/management/backups/', BackupManagementAPIView.as_view(), name='api-management-backups'),
    path('api/management/backups/<int:backup_id>/', BackupManagementDetailAPIView.as_view(), name='api-management-backup-detail'),
    
    # API для поддержки
    path('api/support/', SupportTicketAPIView.as_view(), name='api-support'),
    path('api/support/<int:ticket_id>/', SupportTicketDetailAPIView.as_view(), name='api-support-detail'),
    
    # API для каталога
    path('api/catalog/', CatalogAPIView.as_view(), name='api-catalog'),
    
    # API для избранного
    path('api/favorites/', FavoritesAPIView.as_view(), name='api-favorites'),
    path('api/favorites/<int:product_id>/', FavoriteDetailAPIView.as_view(), name='api-favorite-detail'),
    
    # API для отзывов
    path('api/products/<int:product_id>/reviews/', ProductReviewAPIView.as_view(), name='api-product-reviews'),

    # Старые endpoints (для обратной совместимости, можно будет удалить после переписывания фронтенда)
    path('favorites/add/', views.add_to_favorites, name='api-favorites-add'),
    path('favorites/remove/<int:product_id>/', views.remove_from_favorites, name='remove_from_favorites'),
    path('product/<int:product_id>/status/', views.check_product_status, name='check_product_status'),

    # Добавление в корзину
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove-product/<int:product_id>/', views.remove_from_cart_by_product, name='remove_from_cart_by_product'),
    path('cart/', views.cart_view, name='cart'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('custom-admin-login/', views.custom_admin_login, name='custom_admin_login'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('checkout/', views.checkout, name='checkout'),
    path('cart/update-size/<int:item_id>/', views.update_cart_size, name='update_cart_size'),
    
    # Management (custom) - Админ панель
    path('management/', views.management_dashboard, name='management_dashboard'),
    path('management/users/', views.management_users_list, name='management_users_list'),
    path('management/users/<int:user_id>/edit/', views.management_user_edit, name='management_user_edit'),
    path('management/users/<int:user_id>/toggle-block/', views.management_user_toggle_block, name='management_user_toggle_block'),
    path('management/orders/', views.management_orders_list, name='management_orders_list'),
    path('management/orders/<int:order_id>/status/', views.management_order_change_status, name='management_order_change_status'),
    path('management/analytics/export.csv', views.management_analytics_export_csv, name='management_analytics_export_csv'),
    path('management/promotions/', views.management_promotions_list, name='management_promotions_list'),
    path('management/promotions/add/', views.management_promotion_add, name='management_promotion_add'),
    path('management/promotions/<int:promo_id>/edit/', views.management_promotion_edit, name='management_promotion_edit'),
    path('management/promotions/<int:promo_id>/delete/', views.management_promotion_delete, name='management_promotion_delete'),
    
    
    # Отзывы на товары
    path('product/<int:product_id>/reviews/', views.get_product_reviews, name='get_product_reviews'),
    path('product/<int:product_id>/reviews/page/', views.product_reviews_page, name='product_reviews_page'),
    path('product/<int:product_id>/review/add/', views.add_review, name='add_review'),
    
    # Валидация промокода
    path('checkout/promo/validate/', views.validate_promo, name='validate_promo'),
    
    # Техническая поддержка
    path('support/', views.support_view, name='support'),
    path('support/create/', views.create_support_ticket, name='create_support_ticket'),
    path('support/<int:ticket_id>/', views.support_ticket_detail, name='support_ticket_detail'),
    
    # Панель менеджера
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    
    # Управление товарами
    path('manager/products/', views.manager_products_list, name='manager_products_list'),
    path('manager/products/add/', views.manager_product_add, name='manager_product_add'),
    path('manager/products/<int:product_id>/edit/', views.manager_product_edit, name='manager_product_edit'),
    path('manager/products/<int:product_id>/delete/', views.manager_product_delete, name='manager_product_delete'),
    
    # Управление категориями и брендами
    path('manager/categories/', views.manager_categories_list, name='manager_categories_list'),
    path('manager/categories/add/', views.manager_category_add, name='manager_category_add'),
    path('manager/categories/<int:category_id>/edit/', views.manager_category_edit, name='manager_category_edit'),
    path('manager/brands/add/', views.manager_brand_add, name='manager_brand_add'),
    path('manager/brands/<int:brand_id>/edit/', views.manager_brand_edit, name='manager_brand_edit'),
    
    # Управление заказами
    path('manager/orders/', views.manager_orders_list, name='manager_orders_list'),
    path('manager/orders/<int:order_id>/', views.manager_order_detail, name='manager_order_detail'),
    
    # Управление пользователями
    path('manager/users/', views.manager_users_list, name='manager_users_list'),
    path('manager/users/<int:user_id>/toggle-block/', views.manager_user_toggle_block, name='manager_user_toggle_block'),
    
    # Управление поддержкой
    path('manager/support/', views.manager_support_list, name='manager_support_list'),
    path('manager/support/<int:ticket_id>/', views.manager_support_detail, name='manager_support_detail'),
    
    # Аналитика
    path('manager/analytics/', views.manager_analytics, name='manager_analytics'),
    path('manager/analytics/export.csv', views.manager_analytics_export_csv, name='manager_analytics_export_csv'),
    path('manager/analytics/export.pdf', views.manager_analytics_export_pdf, name='manager_analytics_export_pdf'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)