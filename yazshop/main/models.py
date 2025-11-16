from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum, F

# ==== Роли пользователей ====
class Role(models.Model):
    role_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.role_name


# ==== Профили пользователей ====
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    user_status = models.CharField(max_length=50, default='active')
    registered_at = models.DateTimeField(auto_now_add=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    secret_word = models.CharField(max_length=255, blank=True, null=True, verbose_name='Секретное слово', help_text='Используется для восстановления пароля и подтверждения важных действий')

    def save(self, *args, **kwargs):
        # Если full_name пустой, подтягиваем из User
        if not self.full_name:
            self.full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        # Баланс пользователя может быть отрицательным (долг), но это должно быть контролируемо
        # В данном случае оставляем без ограничений, так как это внутренний баланс
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.user.username


# ==== Адреса пользователей ====
class UserAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_title = models.CharField(max_length=100, blank=True, null=True)
    city_name = models.CharField(max_length=100)
    street_name = models.CharField(max_length=100)
    house_number = models.CharField(max_length=20)
    apartment_number = models.CharField(max_length=20, blank=True, null=True)
    postal_code = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.city_name}, {self.street_name} {self.house_number}"


# ==== Категории ====
class Category(models.Model):
    category_name = models.CharField(max_length=100)
    category_description = models.TextField(blank=True, null=True)
    parent_category = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories'
    )

    def __str__(self):
        return self.category_name


# ==== Бренды ====
class Brand(models.Model):
    brand_name = models.CharField(max_length=100, unique=True)
    brand_country = models.CharField(max_length=100, blank=True, null=True)
    brand_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.brand_name


# ==== Поставщики ====
class Supplier(models.Model):
    supplier_name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    supply_country = models.CharField(max_length=100, blank=True, null=True)
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    supplier_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.supplier_name


# ==== Товары ====
class Product(models.Model):
    product_name = models.CharField(max_length=255)
    
    # Главная фотография
    main_image_url = models.URLField(blank=True, null=True)
    
    # Дополнительные фотографии
    image_url_1 = models.URLField(blank=True, null=True)
    image_url_2 = models.URLField(blank=True, null=True)
    image_url_3 = models.URLField(blank=True, null=True)
    image_url_4 = models.URLField(blank=True, null=True)
    
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    product_description = models.TextField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.product_name
    
    def save(self, *args, **kwargs):
        # Автоматически отключаем товар, если он закончился
        if self.stock_quantity <= 0:
            self.is_available = False
        super().save(*args, **kwargs)

    @property
    def final_price(self):
        try:
            return (self.price or Decimal('0')) * (Decimal('1') - (self.discount or Decimal('0')) / Decimal('100'))
        except Exception:
            return self.price

    @property
    def is_new(self):
        added = self.added_at
        if not added:
            return False
        return added >= timezone.now() - timezone.timedelta(days=30)

# ==== Размеры товаров ====
class ProductSize(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='sizes')
    size_label = models.CharField(max_length=20)
    size_type = models.CharField(max_length=50, blank=True, null=True)
    size_stock = models.IntegerField(default=0)

    class Meta:
        unique_together = ('product', 'size_label')  # запрещаем дубли размеров

    def __str__(self):
        return f"{self.product.product_name} - {self.size_label}"

    def clean(self):
        # Проверяем оставшийся запас
        total_allocated = self.product.sizes.exclude(pk=self.pk).aggregate(
            total=models.Sum('size_stock')
        )['total'] or 0

        remaining_stock = self.product.stock_quantity - total_allocated

        if self.size_stock > remaining_stock:
            raise ValidationError(
                f"Невозможно назначить {self.size_stock} для этого размера. "
                f"Остаток на складе для распределения: {remaining_stock}."
            )

        # Проверка на дубли размеров
        existing_sizes = ProductSize.objects.filter(product=self.product, size_label=self.size_label)
        if self.pk:
            existing_sizes = existing_sizes.exclude(pk=self.pk)
        if existing_sizes.exists():
            raise ValidationError(f"Размер '{self.size_label}' для этого продукта уже существует.")

    def save(self, *args, **kwargs):
        self.full_clean()  # обязательно вызываем clean перед сохранением
        super().save(*args, **kwargs)


# ==== Теги ====
class Tag(models.Model):
    tag_name = models.CharField(max_length=100, unique=True)
    tag_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.tag_name


# ==== Связь товаров и тегов ====
class ProductTag(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('product', 'tag')


# ==== Избранное ====
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')


# ==== Корзина ====
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return self.items.aggregate(
            total=Sum(F('unit_price') * F('quantity'))
        )['total'] or 0

    def __str__(self):
        return f"Корзина {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(ProductSize, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product} x {self.quantity}"


# ==== Заказы ====
class Order(models.Model):
    ORDER_STATUSES = [
        ('processing', 'В обработке'),
        ('paid', 'Оплачен'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.ForeignKey(UserAddress, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1000.00'), verbose_name='Стоимость доставки')
    created_at = models.DateTimeField(auto_now_add=True)
    order_status = models.CharField(max_length=50, default='processing', choices=ORDER_STATUSES)
    promo_code = models.ForeignKey('Promotion', on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_from_balance = models.BooleanField(default=False)
    can_be_cancelled = models.BooleanField(default=True)  # Можно отменить только до отправки
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('13.00'), verbose_name='Налог на прибыль (%)')
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Сумма налога (13%)')

    def __str__(self):
        return f"Order #{self.id}"
    
    def can_cancel(self):
        """Проверяет, можно ли отменить заказ"""
        return self.can_be_cancelled and self.order_status in ['processing', 'paid']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.ForeignKey(ProductSize, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


# ==== Платежи ====
class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=50)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=50)
    paid_at = models.DateTimeField(blank=True, null=True)
    saved_payment_method = models.ForeignKey('SavedPaymentMethod', on_delete=models.SET_NULL, null=True, blank=True)
    promo_code = models.ForeignKey('Promotion', on_delete=models.SET_NULL, null=True, blank=True)

# ==== Сохраненные способы оплаты ====
class SavedPaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_payment_methods')
    card_number = models.CharField(max_length=16)  # Последние 4 цифры для отображения
    card_holder_name = models.CharField(max_length=100)
    expiry_month = models.CharField(max_length=2)
    expiry_year = models.CharField(max_length=4)
    card_type = models.CharField(max_length=20, blank=True, null=True)  # visa, mastercard и т.д.
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Баланс на карте
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.card_type or 'Card'} ****{self.card_number[-4:]}"
    
    def mask_card_number(self):
        """Возвращает замаскированный номер карты"""
        if len(self.card_number) >= 4:
            return f"**** **** **** {self.card_number[-4:]}"
        return "**** **** **** ****"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для проверки, что баланс не может быть отрицательным"""
        if self.balance < 0:
            raise ValueError("Баланс карты не может быть отрицательным")
        super().save(*args, **kwargs)

# ==== Транзакции по картам ====
class CardTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Пополнение баланса'),
        ('withdrawal', 'Вывод на карту'),
    ]
    
    saved_payment_method = models.ForeignKey(SavedPaymentMethod, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed')  # completed, pending, failed
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} ₽ ({self.saved_payment_method.mask_card_number()})"


# ==== Доставка ====
class Delivery(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    carrier_name = models.CharField(max_length=100, blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    delivery_status = models.CharField(max_length=50, blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)


# ==== Промоакции ====
class Promotion(models.Model):
    promo_code = models.CharField(max_length=50, unique=True)
    promo_description = models.TextField(blank=True, null=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.promo_code


# ==== Отзывы ====
class ProductReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    rating_value = models.IntegerField()
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product} - {self.rating_value}/5"


# ==== Поддержка ====
class SupportTicket(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_tickets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets', verbose_name='Ответственный менеджер')
    subject = models.CharField(max_length=200)
    message_text = models.TextField()
    response_text = models.TextField(blank=True, null=True)
    ticket_status = models.CharField(max_length=50, default='new')
    created_at = models.DateTimeField(auto_now_add=True)


# ==== Логи активности ====
class DatabaseBackup(models.Model):
    """Модель для хранения информации о бэкапах базы данных"""
    BACKUP_SCHEDULE_CHOICES = [
        ('now', 'Прямо сейчас'),
        ('weekly', 'Каждую неделю'),
        ('monthly', 'Раз в месяц'),
        ('yearly', 'Раз в год'),
    ]
    
    backup_file = models.FileField(upload_to='backups/', null=True, blank=True)
    backup_name = models.CharField(max_length=255, verbose_name='Название бэкапа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Создан пользователем')
    file_size = models.BigIntegerField(default=0, verbose_name='Размер файла (байт)')
    schedule = models.CharField(max_length=20, choices=BACKUP_SCHEDULE_CHOICES, default='now', verbose_name='Расписание')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания')
    is_automatic = models.BooleanField(default=False, verbose_name='Автоматический бэкап')
    
    class Meta:
        verbose_name = 'Бэкап базы данных'
        verbose_name_plural = 'Бэкапы базы данных'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.backup_name} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
    def get_file_size_mb(self):
        """Возвращает размер файла в МБ"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=50)
    target_object = models.CharField(max_length=100)
    action_description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)

# ==== Транзакции баланса ====
class BalanceTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Пополнение'),
        ('withdrawal', 'Вывод'),
        ('order_payment', 'Оплата заказа'),
        ('order_refund', 'Возврат заказа'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed')  # completed, pending, failed
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} ₽ ({self.user.username})"

# ==== Чеки ====
class ReceiptConfig(models.Model):
    company_name = models.CharField(max_length=255, default='ООО «YazShop»')
    company_inn = models.CharField(max_length=20, default='7700000000')
    company_address = models.CharField(max_length=255, default='г. Москва, ул. Примерная, д. 1')
    cashier_name = models.CharField(max_length=255, default='Кассир')
    shift_number = models.CharField(max_length=50, default='1')
    kkt_rn = models.CharField(max_length=32, default='0000000000000000')  # РН ККТ
    kkt_sn = models.CharField(max_length=32, default='1234567890')        # ЗН ККТ
    fn_number = models.CharField(max_length=32, default='0000000000000000')  # ФН
    site_fns = models.CharField(max_length=100, default='www.nalog.ru')

    class Meta:
        verbose_name = 'Настройки чека'
        verbose_name_plural = 'Настройки чеков'

    def __str__(self):
        return 'Настройки чека'


class Receipt(models.Model):
    STATUS_CHOICES = [
        ('executed', 'Исполнен'),
        ('annulled', 'Аннулирован'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='receipts')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='receipt')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='executed')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Сумма товаров')
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Доставка')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Скидка')
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=20, default='cash')  # cash/card/balance
    number = models.CharField(max_length=50, blank=True, null=True)   # Чек №

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Чек #{self.id} по заказу #{self.order_id}"


class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    article = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


# ==== Счет организации ====
class OrganizationAccount(models.Model):
    """Счет организации (магазина) для хранения средств от продаж"""
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Баланс')
    tax_reserve = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Резерв на налоги (13%)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Счет организации'
        verbose_name_plural = 'Счет организации'
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='org_account_balance_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(tax_reserve__gte=0),
                name='org_account_tax_reserve_non_negative'
            ),
        ]
    
    def __str__(self):
        return f"Счет организации: {self.balance} ₽ (Налог: {self.tax_reserve} ₽)"
    
    @classmethod
    def get_account(cls):
        """Получает или создает единственный счет организации"""
        account, created = cls.objects.get_or_create(pk=1)
        return account
    
    def can_withdraw(self, amount):
        """Проверяет, можно ли вывести указанную сумму"""
        return self.balance >= amount
    
    def can_pay_tax(self, amount):
        """Проверяет, можно ли оплатить налог на указанную сумму"""
        return self.balance >= amount and self.tax_reserve >= amount


# ==== Транзакции счета организации ====
class OrganizationTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('order_payment', 'Поступление от заказа'),
        ('order_refund', 'Возврат по отмене заказа'),
        ('tax_payment', 'Оплата налога'),
        ('withdrawal', 'Вывод на карту админа'),
    ]
    
    organization_account = models.ForeignKey(OrganizationAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='org_transactions')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создано пользователем')
    created_at = models.DateTimeField(auto_now_add=True)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_reserve_before = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_reserve_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Транзакция счета организации'
        verbose_name_plural = 'Транзакции счета организации'
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} ₽ ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
