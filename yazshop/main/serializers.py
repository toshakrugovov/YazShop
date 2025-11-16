from rest_framework import serializers
from .models import (
	Role, UserProfile, UserAddress, Category, Brand, Supplier, Product, ProductSize,
	Tag, ProductTag, Favorite, Cart, CartItem, Order, OrderItem, Payment,
	Delivery, Promotion, ProductReview, SupportTicket, ActivityLog,
	SavedPaymentMethod, CardTransaction, BalanceTransaction, Receipt, ReceiptItem,
	OrganizationAccount, OrganizationTransaction
)

class RoleSerializer(serializers.ModelSerializer):
	class Meta:
		model = Role
		fields = '__all__'

class UserAddressSerializer(serializers.ModelSerializer):
	class Meta:
		model = UserAddress
		fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
	user = serializers.StringRelatedField()
	class Meta:
		model = UserProfile
		fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
	class Meta:
		model = Category
		fields = '__all__'

class BrandSerializer(serializers.ModelSerializer):
	class Meta:
		model = Brand
		fields = '__all__'

class SupplierSerializer(serializers.ModelSerializer):
	class Meta:
		model = Supplier
		fields = '__all__'

class ProductSizeSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProductSize
		fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
	final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
	is_new = serializers.BooleanField(read_only=True)
	class Meta:
		model = Product
		fields = '__all__'

class TagSerializer(serializers.ModelSerializer):
	class Meta:
		model = Tag
		fields = '__all__'

class ProductTagSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProductTag
		fields = '__all__'

class FavoriteSerializer(serializers.ModelSerializer):
	class Meta:
		model = Favorite
		fields = '__all__'

class CartSerializer(serializers.ModelSerializer):
	class Meta:
		model = Cart
		fields = '__all__'

class CartItemSerializer(serializers.ModelSerializer):
	class Meta:
		model = CartItem
		fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
	class Meta:
		model = Order
		fields = '__all__'

class OrderItemSerializer(serializers.ModelSerializer):
	class Meta:
		model = OrderItem
		fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
	class Meta:
		model = Payment
		fields = '__all__'

class DeliverySerializer(serializers.ModelSerializer):
	class Meta:
		model = Delivery
		fields = '__all__'

class PromotionSerializer(serializers.ModelSerializer):
	class Meta:
		model = Promotion
		fields = '__all__'

class ProductReviewSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProductReview
		fields = '__all__'

class SupportTicketSerializer(serializers.ModelSerializer):
	class Meta:
		model = SupportTicket
		fields = '__all__'

class ActivityLogSerializer(serializers.ModelSerializer):
	class Meta:
		model = ActivityLog
		fields = '__all__'

class SavedPaymentMethodSerializer(serializers.ModelSerializer):
	class Meta:
		model = SavedPaymentMethod
		fields = '__all__'

class CardTransactionSerializer(serializers.ModelSerializer):
	class Meta:
		model = CardTransaction
		fields = '__all__'

class BalanceTransactionSerializer(serializers.ModelSerializer):
	class Meta:
		model = BalanceTransaction
		fields = '__all__'

class ReceiptSerializer(serializers.ModelSerializer):
	class Meta:
		model = Receipt
		fields = '__all__'

class ReceiptItemSerializer(serializers.ModelSerializer):
	class Meta:
		model = ReceiptItem
		fields = '__all__'

class OrganizationAccountSerializer(serializers.ModelSerializer):
	class Meta:
		model = OrganizationAccount
		fields = '__all__'

class OrganizationTransactionSerializer(serializers.ModelSerializer):
	class Meta:
		model = OrganizationTransaction
		fields = '__all__'
