from django.contrib import admin
from .models import (
    Product, ProductSize, Tag, ProductTag, Cart, CartItem,
    Order, OrderItem, Payment, Delivery, Promotion,
    ProductReview, SupportTicket, ActivityLog, Category, Brand, Supplier, Role, UserAddress, UserProfile,
    Receipt, ReceiptItem, ReceiptConfig, DatabaseBackup
)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'role_name')
    search_fields = ('role_name',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'role', 'user_status', 'registered_at')
    list_filter = ('user_status', 'role')
    search_fields = ('user__username', 'user__email', 'full_name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'category_name', 'parent_category')
    list_filter = ('parent_category',)
    search_fields = ('category_name',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand_name', 'brand_country')
    search_fields = ('brand_name', 'brand_country')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier_name', 'contact_person', 'supply_country')
    search_fields = ('supplier_name', 'contact_person')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_name', 'category', 'brand', 'price', 'discount', 'stock_quantity', 'is_available', 'added_at')
    list_filter = ('category', 'brand', 'is_available')
    search_fields = ('product_name', 'product_description')

@admin.register(ProductSize)
class ProductSizeAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'size_label', 'size_type', 'size_stock')
    list_filter = ('size_type',)
    search_fields = ('size_label', 'product__product_name')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'tag_name')
    search_fields = ('tag_name',)

@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ('product', 'tag')
    search_fields = ('product__product_name', 'tag__tag_name')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at')
    search_fields = ('user__username',)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'size', 'quantity', 'unit_price')
    search_fields = ('product__product_name', 'cart__user__username')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'address', 'total_amount', 'order_status', 'created_at')
    list_filter = ('order_status',)
    search_fields = ('user__username', 'address__address_title')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'size', 'quantity', 'unit_price')
    search_fields = ('product__product_name', 'order__user__username')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'payment_method', 'payment_amount', 'payment_status', 'paid_at')
    list_filter = ('payment_method', 'payment_status')
    search_fields = ('order__user__username',)

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'carrier_name', 'tracking_number', 'delivery_status', 'shipped_at', 'delivered_at')
    list_filter = ('delivery_status',)
    search_fields = ('carrier_name', 'tracking_number')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('id', 'promo_code', 'discount', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('promo_code', 'promo_description')

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'rating_value', 'created_at')
    list_filter = ('rating_value',)
    search_fields = ('user__username', 'product__product_name')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'ticket_status', 'created_at')
    list_filter = ('ticket_status',)
    search_fields = ('subject', 'user__username')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'action_type', 'target_object', 'created_at', 'ip_address')
    list_filter = ('action_type',)
    search_fields = ('user__username', 'target_object', 'action_description')

@admin.register(ReceiptConfig)
class ReceiptConfigAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'company_inn', 'cashier_name', 'shift_number')

class ReceiptItemInline(admin.TabularInline):
    model = ReceiptItem
    extra = 0
    readonly_fields = ('product_name', 'article', 'quantity', 'unit_price', 'line_total', 'vat_amount')

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'created_at', 'status', 'total_amount', 'vat_amount', 'payment_method')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('order__id', 'user__username', 'number')
    inlines = [ReceiptItemInline]

@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ('id', 'backup_name', 'created_at', 'created_by', 'get_file_size_mb', 'schedule', 'is_automatic')
    list_filter = ('schedule', 'is_automatic', 'created_at')
    search_fields = ('backup_name', 'notes')
    readonly_fields = ('created_at', 'file_size', 'backup_file')
    fieldsets = (
        ('Основная информация', {
            'fields': ('backup_name', 'backup_file', 'created_at', 'created_by', 'file_size')
        }),
        ('Настройки', {
            'fields': ('schedule', 'is_automatic', 'notes')
        }),
    )