from django.shortcuts import render, get_object_or_404, redirect
import os
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Avg, F, Exists, OuterRef, Q, Count, Sum
from django.views.decorators.http import require_POST
from django import forms
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from decimal import Decimal, InvalidOperation
import json
from datetime import timedelta

from .models import (
    Role, Product, Promotion, Tag, Category, Brand, Favorite, UserProfile,
    UserAddress, Order, OrderItem, Cart, CartItem, ProductReview, SupportTicket, Payment, SavedPaymentMethod, ProductSize, BalanceTransaction, CardTransaction, Receipt, ReceiptItem, ReceiptConfig, Supplier, Delivery, ProductTag, ActivityLog, DatabaseBackup, OrganizationAccount, OrganizationTransaction
)

# =================== Форма для профиля ===================
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['full_name', 'phone_number', 'birth_date', 'secret_word']
        widgets = {
            'secret_word': forms.TextInput(attrs={'type': 'password', 'placeholder': 'Введите секретное слово'}),
        }

# =================== Главная страница ===================
def handler404(request, exception=None):
    """Кастомная обработка ошибки 404"""
    from django.shortcuts import render
    return render(request, '404.html', status=404)

def home(request):
    new_products = Product.objects.filter(is_available=True).order_by('-added_at')[:12]
    popular_products = Product.objects.filter(is_available=True).order_by('-added_at')[:12]
    promotions = Promotion.objects.filter(is_active=True).order_by('-start_date')[:5]
    tags = Tag.objects.all()[:10]
    categories = Category.objects.all()[:10]

    return render(request, 'home.html', {
        'new_products': new_products,
        'popular_products': popular_products,
        'promotions': promotions,
        'tags': tags,
        'categories': categories
    })

# =================== Авторизация и регистрация ===================
def login_view(request):
    # Очищаем все сообщения, которые не относятся к странице входа
    # Оставляем только сообщения об ошибках блокировки
    storage = messages.get_messages(request)
    messages_to_keep = []
    for message in storage:
        msg_text = str(message).lower()
        # Оставляем только сообщения о блокировке аккаунта
        if 'заблокирован' in msg_text or 'https://t.me/toshaplenka' in str(message):
            messages_to_keep.append(str(message))
    # Очищаем все сообщения (включая success messages типа "Пользователь обновлен")
    storage.used = True
    # Добавляем обратно только нужные сообщения об ошибках
    for msg in messages_to_keep:
        messages.error(request, msg)
    return render(request, 'login.html')

def register_view(request):
    return render(request, 'register.html')

# =================== Информационные страницы ===================
def contacts(request):
    return render(request, 'contacts.html')

def refund(request):
    return render(request, 'refund.html')

def bonus(request):
    return render(request, 'bonus.html')

def delivery(request):
    return render(request, 'delivery.html')

def about(request):
    return render(request, 'about.html')

# =================== Каталог ===================
def catalog(request):
    products = Product.objects.filter(is_available=True)
    categories = Category.objects.all()
    brands = Brand.objects.all()
    tags = Tag.objects.all()

    query = request.GET.get('q')
    if query:
        products = products.filter(product_name__icontains=query)

    category_id = request.GET.get('category')
    brand_id = request.GET.get('brand')
    tag_id = request.GET.get('tag')
    sort = request.GET.get('sort')

    if category_id:
        products = products.filter(category_id=category_id)
    if brand_id:
        products = products.filter(brand_id=brand_id)
    if tag_id:
        products = products.filter(producttag__tag_id=tag_id)

    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'popular':
        products = products.order_by('-stock_quantity')

    return render(request, 'catalog.html', {
        'products': products,
        'categories': categories,
        'brands': brands,
        'tags': tags,
        'request': request,
    })

# =================== Избранное ===================
def favorites(request):
    if not request.user.is_authenticated:
        return redirect('login')
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    return render(request, 'favorites.html', {'favorites': favorites})

@login_required
@require_POST
def add_to_favorites(request):
    data = json.loads(request.body)
    product_id = data.get('product')
    try:
        product = Product.objects.get(id=product_id)
        Favorite.objects.get_or_create(user=request.user, product=product)
        return JsonResponse({'status': 'ok'})
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Продукт не найден'}, status=404)

@login_required
@require_POST
def remove_from_favorites(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Favorite.objects.filter(user=request.user, product=product).delete()
    return JsonResponse({'status': 'ok'})

def check_product_status(request, product_id):
    """Проверяет, находится ли товар в избранном и корзине"""
    product = get_object_or_404(Product, id=product_id)
    
    if not request.user.is_authenticated:
        return JsonResponse({
            'is_favorite': False,
            'is_in_cart': False
        })
    
    is_favorite = Favorite.objects.filter(user=request.user, product=product).exists()
    
    # Проверяем, есть ли товар в корзине (любой размер)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    is_in_cart = CartItem.objects.filter(cart=cart, product=product).exists()
    
    return JsonResponse({
        'is_favorite': is_favorite,
        'is_in_cart': is_in_cart
    })

@login_required
@require_POST
def remove_from_cart_by_product(request, product_id):
    """Удаляет товар из корзины по product_id (удаляет все позиции этого товара)"""
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.filter(cart=cart, product=product).delete()
    return JsonResponse({'success': True, 'cart_count': cart.items.count()})

@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.select_related('product', 'size').all()

    # Подготовим словарь: product_id → список размеров
    product_sizes = {
        item.product.id: list(item.product.sizes.all())
        for item in cart_items
    }

    return render(request, 'cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'product_sizes': product_sizes
    })


from django.http import JsonResponse
from .models import Product, CartItem, ProductSize, Cart

# =================== Профиль пользователя ===================
@login_required
def profile_view(request):
    # Получаем профиль или создаем, чтобы существовал объект UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Формируем full_name из встроенного пользователя
    full_name = f"{request.user.first_name} {request.user.last_name}".strip()

    orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]

    # Собираем уведомления для профиля (без отдельной таблицы)
    notifications = []
    try:
        # 1) Изменение статуса заказов (последние)
        recent_orders = Order.objects.filter(user=request.user).order_by('-updated_at' if hasattr(Order, 'updated_at') else '-created_at')[:10]
        for o in recent_orders:
            status_label = {
                'processing': 'В обработке',
                'paid': 'Оплачен',
                'shipped': 'Отправлен',
                'delivered': 'Доставлен',
                'cancelled': 'Отменен',
            }.get(o.order_status, o.order_status)
            notifications.append({
                'id': f'order-status-{o.id}',
                'type': 'order',
                'text': f'Статус вашего заказа #{o.id} изменился: {status_label}',
                'url': request.build_absolute_uri(
                    request.path.replace('profile/', f'profile/orders/{o.id}/')
                ) if 'profile/' in request.path else '',
            })
        # 2) Возвраты на баланс
        refunds = BalanceTransaction.objects.filter(user=request.user, transaction_type='order_refund').order_by('-created_at')[:5]
        for r in refunds:
            order_id = r.order_id if hasattr(r, 'order_id') else (r.order.id if getattr(r, 'order', None) else '')
            notifications.append({
                'id': f'refund-{r.id}',
                'type': 'refund',
                'text': f'Вам возвращены деньги {r.amount} ₽ за заказ #{order_id}',
                'url': '',
            })
        # 3) Новые активные промокоды (последние активированные по дате начала)
        from django.utils import timezone
        today = timezone.now().date()
        promos = Promotion.objects.filter(is_active=True).order_by('-start_date')[:5]
        for p in promos:
            # Показываем только относительно свежие промо (за последние 30 дней)
            if not p.start_date or (today - p.start_date).days <= 30:
                notifications.append({
                    'id': f'promo-{p.id}',
                    'type': 'promo',
                    'text': f'Новый промокод: {p.promo_code} — скидка {p.discount}%',
                    'url': '',
                })
    except Exception:
        # Если что-то пошло не так, просто не показываем уведомления
        notifications = []

    return render(request, 'profile/profile.html', {
        'profile': profile,
        'full_name': full_name,
        'orders': orders,
        'notifications': notifications[:8]  # ограничим количество
    })

@login_required
def notifications_view(request):
    """
    Страница всех уведомлений.
    Уведомления берутся из localStorage на клиенте, здесь только оболочка.
    """
    return render(request, 'profile/notifications.html')


@login_required
def edit_profile(request):
    user = request.user

    # Получаем существующий профиль, не создаём новый автоматически
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile(user=user)  # создаём только если реально нет

    if request.method == 'POST':
        # Определяем, это JSON-запрос (AJAX) или обычная форма
        is_json = request.headers.get('Content-Type', '').startswith('application/json')
        if is_json:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
                first_name = str(payload.get('first_name', '')).strip()
                last_name = str(payload.get('last_name', '')).strip()
                phone_number = str(payload.get('phone_number', '')).strip()
                birth_date_str = str(payload.get('birth_date', '')).strip()
                secret_word = str(payload.get('secret_word', '')).strip()
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)
        else:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            birth_date_str = request.POST.get('birth_date', '').strip()  # YYYY-MM-DD
            secret_word = request.POST.get('secret_word', '').strip()

        # Валидация
        if not first_name or not last_name:
            if is_json:
                return JsonResponse({'success': False, 'error': 'Имя и Фамилия обязательны'}, status=400)
            messages.error(request, 'Имя и Фамилия обязательны.')
        else:
            # Обновляем User
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Обновляем профиль
            profile.phone_number = phone_number
            if birth_date_str:
                try:
                    from datetime import datetime as _dt
                    profile.birth_date = _dt.strptime(birth_date_str, '%Y-%m-%d').date()
                except ValueError:
                    if is_json:
                        return JsonResponse({'success': False, 'error': 'Неверный формат даты рождения. Используйте ГГГГ-ММ-ДД.'}, status=400)
                    messages.error(request, 'Неверный формат даты рождения. Используйте ГГГГ-ММ-ДД.')
            # Обновляем секретное слово только если оно указано
            if secret_word:
                profile.secret_word = secret_word
            profile.save()

            if is_json:
                return JsonResponse({'success': True})
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('profile')

    # Контекст для шаблона
    context = {
        'user': user,
        'profile': profile,  # подтягиваем существующие значения
    }

    return render(request, 'edit_profile.html', context)

@login_required
def delete_account(request):
    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Ваш аккаунт удален.")
        return redirect('home')
    return redirect('profile')

# =================== История заказов ===================
@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "profile/order_history.html", {"orders": orders})

@login_required
def order_detail_view(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    items = order.items.select_related("product", "size").all()
    # Вычисляем общую сумму для каждого товара
    items_with_total = []
    for item in items:
        item_total = float(item.unit_price) * item.quantity
        items_with_total.append({
            'item': item,
            'total': item_total
        })
    return render(request, "profile/order_detail.html", {
        "order": order,
        "items": items,
        "items_with_total": items_with_total
    })

@login_required
@require_POST
def cancel_order(request, pk):
    """Отмена заказа с возвратом денег и товара на склад"""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    
    if not order.can_cancel():
        messages.error(request, "Этот заказ нельзя отменить.")
        return redirect('order_detail', pk=order.pk)
    
    # Возвращаем товар на склад
    # ВАЖНО: сначала обновляем product.stock_quantity, потом size_stock,
    # чтобы валидация ProductSize.clean() не выдавала ошибку
    # Используем update() для обхода валидации при возврате товара
    for item in order.items.all():
        if item.product:
            # Сначала увеличиваем общий запас товара
            # Используем F() для атомарного обновления в БД
            Product.objects.filter(pk=item.product.pk).update(
                stock_quantity=F('stock_quantity') + item.quantity
            )
            
            # Обновляем объект из БД для дальнейшего использования
            item.product.refresh_from_db()
            
            # Проверяем и обновляем статус доступности товара
            if item.product.stock_quantity <= 0:
                item.product.is_available = False
                item.product.save(update_fields=['is_available'])
            
            # Потом увеличиваем запас конкретного размера (если есть)
            # Используем update() чтобы обойти валидацию clean()
            if item.size:
                ProductSize.objects.filter(pk=item.size.pk).update(
                    size_stock=F('size_stock') + item.quantity
                )
    
    # Возвращаем деньги клиенту и списываем со счета организации
    # Проверяем, был ли заказ оплачен (не наличными)
    payment = Payment.objects.filter(order=order).first()
    was_paid = payment and payment.payment_status == 'paid'
    
    with transaction.atomic():
        # Списываем со счета организации только если заказ был оплачен
        if was_paid:
            org_account = OrganizationAccount.get_account()
            org_balance_before = org_account.balance
            org_tax_reserve_before = org_account.tax_reserve
            
            # Списываем сумму заказа
            if org_account.balance < order.total_amount:
                messages.error(request, "Недостаточно средств на счете организации для возврата.")
                return redirect('order_detail', pk=order.pk)
            
            org_account.balance -= order.total_amount
            
            # Возвращаем налог из резерва
            if org_account.tax_reserve >= order.tax_amount:
                org_account.tax_reserve -= order.tax_amount
            else:
                org_account.tax_reserve = Decimal('0.00')
            
            org_account.save()
            
            # Создаем транзакцию списания со счета организации
            OrganizationTransaction.objects.create(
                organization_account=org_account,
                transaction_type='order_refund',
                amount=order.total_amount,
                description=f'Возврат по отмене заказа #{order.id}',
                order=order,
                created_by=request.user,
                balance_before=org_balance_before,
                balance_after=org_account.balance,
                tax_reserve_before=org_tax_reserve_before,
                tax_reserve_after=org_account.tax_reserve
            )
        
        # Возвращаем деньги клиенту
        if order.paid_from_balance:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            balance_before = profile.balance
            profile.balance += order.total_amount
            profile.save()
            
            # Создаем транзакцию возврата
            BalanceTransaction.objects.create(
                user=request.user,
                transaction_type='order_refund',
                amount=order.total_amount,
                balance_before=balance_before,
                balance_after=profile.balance,
                description=f'Возврат за отмененный заказ #{order.id}',
                order=order,
                status='completed'
            )
        elif was_paid and payment and payment.saved_payment_method:
            # Если оплата была картой, возвращаем на карту
            try:
                card = payment.saved_payment_method
                card.balance += order.total_amount
                card.save()
                
                # Создаем транзакцию по карте
                CardTransaction.objects.create(
                    saved_payment_method=card,
                    transaction_type='deposit',
                    amount=order.total_amount,
                    description=f'Возврат за отмененный заказ #{order.id}',
                    status='completed'
                )
            except Exception as e:
                # Если не удалось вернуть на карту, возвращаем на баланс
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.balance += order.total_amount
                profile.save()
                
                BalanceTransaction.objects.create(
                    user=request.user,
                    transaction_type='order_refund',
                    amount=order.total_amount,
                    balance_before=profile.balance - order.total_amount,
                    balance_after=profile.balance,
                    description=f'Возврат за отмененный заказ #{order.id} (карта недоступна)',
                    order=order,
                    status='completed'
                )
    
    # Обновляем статус заказа
    order.order_status = 'cancelled'
    order.can_be_cancelled = False
    order.save()

    # Аннулируем чек, если есть
    try:
        if hasattr(order, 'receipt') and order.receipt:
            order.receipt.status = 'annulled'
            order.receipt.save()
    except Exception:
        pass
    
    _log_activity(request.user, 'update', f'order_{order.id}', 'Заказ отменен пользователем', request)
    messages.success(request, "Заказ отменен. Деньги возвращены на баланс, товар возвращен на склад.")
    return redirect('order_detail', pk=order.pk)

# =================== Способы оплаты ===================
@login_required
def payment_methods_view(request):
    payment_methods = SavedPaymentMethod.objects.filter(user=request.user).prefetch_related('transactions')
    return render(request, 'profile/payment_methods.html', {'payment_methods': payment_methods})

@login_required
@require_POST
def add_payment_method(request):
    card_number = request.POST.get('card_number', '').strip().replace(' ', '')
    card_holder_name = request.POST.get('card_holder_name', '').strip()
    expiry_month = request.POST.get('expiry_month', '').strip()
    expiry_year = request.POST.get('expiry_year', '').strip()
    is_default = request.POST.get('is_default') == 'on'
    
    if not all([card_number, card_holder_name, expiry_month, expiry_year]):
        messages.error(request, "Пожалуйста, заполните все поля.")
        return redirect('payment_methods')
    
    # Определяем тип карты
    card_type = 'visa' if card_number.startswith('4') else 'mastercard' if card_number.startswith('5') else 'card'
    
    # Сохраняем только последние 4 цифры
    card_last_4 = card_number[-4:] if len(card_number) >= 4 else card_number
    
    # Если это основная карта, снимаем флаг с других
    if is_default:
        SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
    
    SavedPaymentMethod.objects.create(
        user=request.user,
        card_number=card_last_4,
        card_holder_name=card_holder_name,
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        card_type=card_type,
        is_default=is_default
    )
    
    messages.success(request, "Способ оплаты добавлен.")
    return redirect('payment_methods')

@login_required
@require_POST
def delete_payment_method(request, payment_id):
    payment = get_object_or_404(SavedPaymentMethod, id=payment_id, user=request.user)
    payment.delete()
    messages.success(request, "Способ оплаты удален.")
    return redirect('payment_methods')

@login_required
@require_POST
def set_default_payment_method(request, payment_id):
    SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
    payment = get_object_or_404(SavedPaymentMethod, id=payment_id, user=request.user)
    payment.is_default = True
    payment.save()
    messages.success(request, "Основной способ оплаты изменен.")
    return redirect('payment_methods')

# =================== Баланс ===================
@login_required
def balance_view(request):
    """Страница управления балансом"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    transactions = BalanceTransaction.objects.filter(user=request.user)[:20]
    saved_payments = SavedPaymentMethod.objects.filter(user=request.user)
    
    return render(request, 'profile/balance.html', {
        'profile': profile,
        'transactions': transactions,
        'saved_payments': saved_payments
    })

@login_required
@require_POST
def deposit_balance(request):
    """Пополнение баланса с карты"""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        card_id = request.POST.get('card_id')
        
        if amount <= 0:
            messages.error(request, "Сумма пополнения должна быть больше нуля.")
            return redirect('balance')
        
        if not card_id:
            messages.error(request, "Пожалуйста, выберите карту для пополнения.")
            return redirect('balance')
        
        # Проверяем, что карта принадлежит пользователю
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        with transaction.atomic():
            # Блокируем строку карты для корректного списания
            card = SavedPaymentMethod.objects.select_for_update().get(id=card.id)
            profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
            if card.balance < amount:
                messages.error(request, f"Недостаточно средств на карте. Баланс карты: {card.balance} ₽")
                return redirect('balance')
            balance_before = profile.balance
            # Списание с карты (проверяем, что баланс не станет отрицательным)
            new_card_balance = card.balance - amount
            if new_card_balance < 0:
                messages.error(request, f"Недостаточно средств на карте. Баланс карты: {card.balance} ₽")
                return redirect('balance')
            card.balance = new_card_balance
            card.save()
            # Пополнение баланса пользователя
            profile.balance += amount
            profile.save()
            
            # Создаем транзакцию баланса
            BalanceTransaction.objects.create(
                user=request.user,
                transaction_type='deposit',
                amount=amount,
                balance_before=balance_before,
                balance_after=profile.balance,
                description=f'Пополнение баланса с карты {card.mask_card_number()}',
                status='completed'
            )
            
            # Создаем транзакцию по карте (списание)
            CardTransaction.objects.create(
                saved_payment_method=card,
                transaction_type='withdrawal',
                amount=amount,
                description=f'Перевод на баланс пользователя {amount} ₽',
                status='completed'
            )
        messages.success(request, f"Баланс пополнен на {amount} ₽ с карты {card.mask_card_number()}. Текущий баланс: {profile.balance} ₽")
    except (ValueError, TypeError):
        messages.error(request, "Неверная сумма.")
    
    return redirect('balance')

@login_required
@require_POST
def withdraw_balance(request):
    """Вывод средств с баланса на карту"""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        card_id = request.POST.get('card_id')
        
        if amount <= 0:
            messages.error(request, "Сумма вывода должна быть больше нуля.")
            return redirect('balance')
        
        if not card_id:
            messages.error(request, "Пожалуйста, выберите карту для вывода.")
            return redirect('balance')
        
        # Проверяем, что карта принадлежит пользователю
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        
        if profile.balance < amount:
            messages.error(request, f"Недостаточно средств на балансе. Текущий баланс: {profile.balance} ₽")
            return redirect('balance')
        
        with transaction.atomic():
            # блокируем профиль и карту
            profile = UserProfile.objects.select_for_update().get(user=request.user)
            card = SavedPaymentMethod.objects.select_for_update().get(id=card.id)
            balance_before = profile.balance
            # Списываем с баланса пользователя
            profile.balance -= amount
            profile.save()
            # Пополняем баланс карты
            card.balance += amount
            card.save()
            
            # Создаем транзакцию баланса
            BalanceTransaction.objects.create(
                user=request.user,
                transaction_type='withdrawal',
                amount=amount,
                balance_before=balance_before,
                balance_after=profile.balance,
                description=f'Вывод средств на карту {card.mask_card_number()}',
                status='completed'
            )
            
            # Создаем транзакцию по карте (пополнение)
            CardTransaction.objects.create(
                saved_payment_method=card,
                transaction_type='deposit',
                amount=amount,
                description=f'Пополнение карты на {amount} ₽ с внутреннего баланса',
                status='completed'
            )
        
        messages.success(request, f"Средства выведены: {amount} ₽ на карту {card.mask_card_number()}. Текущий баланс: {profile.balance} ₽")
    except (ValueError, TypeError):
        messages.error(request, "Неверная сумма.")
    
    return redirect('balance')

@login_required
def get_card_transactions(request, card_id):
    """Получить транзакции по карте (AJAX)"""
    card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
    transactions = CardTransaction.objects.filter(saved_payment_method=card)[:20]
    
    transactions_data = [{
        'id': t.id,
        'type': t.get_transaction_type_display(),
        'amount': float(t.amount),
        'description': t.description,
        'date': t.created_at.strftime('%d.%m.%Y %H:%M'),
        'status': t.status
    } for t in transactions]
    
    return JsonResponse({
        'card': {
            'id': card.id,
            'mask': card.mask_card_number(),
            'type': card.card_type or 'CARD',
            'holder': card.card_holder_name,
            'balance': float(card.balance)
        },
        'transactions': transactions_data
    })

@login_required
@require_POST
def deposit_from_card(request, card_id):
    """Пополнение баланса с конкретной карты"""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Сумма должна быть больше нуля'}, status=400)
        
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        with transaction.atomic():
            card = SavedPaymentMethod.objects.select_for_update().get(id=card.id)
            profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
            if card.balance < amount:
                return JsonResponse({'success': False, 'message': 'Недостаточно средств на карте'}, status=400)
            # Списываем с карты (проверяем, что баланс не станет отрицательным)
            new_card_balance = card.balance - amount
            if new_card_balance < 0:
                return JsonResponse({'success': False, 'message': 'Недостаточно средств на карте'}, status=400)
            card.balance = new_card_balance
            card.save()
            # Пополняем баланс пользователя
            balance_before = profile.balance
            profile.balance += amount
            profile.save()
            
            # Создаем транзакции
            BalanceTransaction.objects.create(
                user=request.user,
                transaction_type='deposit',
                amount=amount,
                balance_before=balance_before,
                balance_after=profile.balance,
                description=f'Пополнение баланса с карты {card.mask_card_number()}',
                status='completed'
            )
            
            CardTransaction.objects.create(
                saved_payment_method=card,
                transaction_type='withdrawal',  # списание с карты при переводе на счет
                amount=amount,
                description=f'Перевод на счет пользователя {amount} ₽',
                status='completed'
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Баланс пополнен на {amount} ₽',
            'new_balance': float(profile.balance),
            'card_balance': float(card.balance)
        })
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Неверная сумма'}, status=400)

@login_required
@require_POST
def withdraw_to_card(request, card_id):
    """Вывод средств на конкретную карту"""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Сумма должна быть больше нуля'}, status=400)
        
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        with transaction.atomic():
            profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
            if profile.balance < amount:
                return JsonResponse({'success': False, 'message': 'Недостаточно средств на внутреннем балансе'}, status=400)
            # блокируем карту
            card = SavedPaymentMethod.objects.select_for_update().get(id=card.id)
            balance_before = profile.balance
            # списываем с баланса профиля
            profile.balance -= amount
            profile.save()
            # пополняем карту
            card.balance += amount
            card.save()
            # транзакция баланса
            BalanceTransaction.objects.create(
                user=request.user,
                transaction_type='withdrawal',
                amount=amount,
                balance_before=balance_before,
                balance_after=profile.balance,
                description=f'Вывод средств на карту {card.mask_card_number()}',
                status='completed'
            )
            # транзакция по карте
            CardTransaction.objects.create(
                saved_payment_method=card,
                transaction_type='deposit',
                amount=amount,
                description=f'Пополнение карты на {amount} ₽',
                status='completed'
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Карта пополнена на {amount} ₽',
            'new_balance': float(profile.balance),
            'card_balance': float(card.balance)
        })
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Неверная сумма'}, status=400)


@login_required
@require_POST
def topup_card_balance(request, card_id):
    """Прямое пополнение баланса конкретной карты (без списания откуда-либо)"""
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Сумма должна быть больше нуля'}, status=400)
        
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        card.balance += amount
        card.save()
        
        # Лог транзакции по карте
        CardTransaction.objects.create(
            saved_payment_method=card,
            transaction_type='deposit',
            amount=amount,
            description=f'Пополнение карты на {amount} ₽',
            status='completed'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Карта пополнена на {amount} ₽',
            'card_balance': float(card.balance)
        })
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Неверная сумма'}, status=400)

# =================== Адреса ===================
@login_required
def addresses_view(request):
    addresses = UserAddress.objects.filter(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            UserAddress.objects.create(
                user=request.user,
                address_title=request.POST.get("address_title", ""),
                city_name=request.POST.get("city_name"),
                street_name=request.POST.get("street_name"),
                house_number=request.POST.get("house_number"),
                apartment_number=request.POST.get("apartment_number", ""),
                postal_code=request.POST.get("postal_code"),
                is_primary=request.POST.get("is_primary") == "on"
            )
            messages.success(request, "Адрес добавлен.")
        elif action == "edit":
            addr_id = request.POST.get("address_id")
            try:
                address = UserAddress.objects.get(id=addr_id, user=request.user)
                address.address_title = request.POST.get("address_title", "")
                address.city_name = request.POST.get("city_name")
                address.street_name = request.POST.get("street_name")
                address.house_number = request.POST.get("house_number")
                address.apartment_number = request.POST.get("apartment_number", "")
                address.postal_code = request.POST.get("postal_code")
                address.is_primary = request.POST.get("is_primary") == "on"
                address.save()
                messages.success(request, "Адрес обновлен.")
            except UserAddress.DoesNotExist:
                messages.error(request, "Адрес не найден.")
        elif action == "delete":
            addr_id = request.POST.get("address_id")
            UserAddress.objects.filter(id=addr_id, user=request.user).delete()
            messages.success(request, "Адрес удален.")
        elif action == "set_primary":
            addr_id = request.POST.get("address_id")
            UserAddress.objects.filter(user=request.user).update(is_primary=False)
            UserAddress.objects.filter(id=addr_id, user=request.user).update(is_primary=True)
            messages.success(request, "Основной адрес изменен.")
        return redirect("addresses")

    return render(request, "profile/addresses.html", {"addresses": addresses})

@login_required
def delete_account(request):
    if request.method == "POST":
        user = request.user
        logout(request)  # разлогиниваем пользователя
        user.delete()    # удаляем аккаунт
        messages.success(request, "Ваш аккаунт был удален.")
        return redirect('home')
    return render(request, 'profile/delete_account.html')

ADMIN_SECRET_MESSAGE = 'privet yaz'
ADMIN_SECRET_CODE = '23051967'

def custom_admin_login(request):
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        code = request.POST.get('secret_code', '').strip()

        if message == ADMIN_SECRET_MESSAGE and code == ADMIN_SECRET_CODE:
            # Сохраняем сессию, чтобы открыть стандартный admin
            request.session['admin_access_granted'] = True
            return redirect('/admin/')  # перенаправляем в стандартный admin
        else:
            messages.error(request, 'Неверное сообщение или секретный код')

    return render(request, 'main/custom_admin_login.html')

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.forms import modelform_factory

def _format_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))} ₽"

# Импорт вспомогательных функций из helpers.py
from .helpers import _user_is_admin, _user_is_manager, _log_activity

@login_required
def management_dashboard(request):
    """Расширенная панель администратора"""
    if not _user_is_admin(request.user):
        messages.error(request, "Доступ запрещен. Требуется роль администратора.")
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'admin_dashboard', 'Просмотр панели администратора', request)
    
    from django.db.models import Count, Sum
    from django.utils import timezone
    from datetime import timedelta
    
    # Статистика для дашборда
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_tickets = SupportTicket.objects.count()
    new_tickets = SupportTicket.objects.filter(ticket_status='new').count()
    recent_logs = ActivityLog.objects.select_related('user').order_by('-created_at')[:10]
    
    # Активность за последние 7 дней
    week_ago = timezone.now() - timedelta(days=7)
    recent_activity = ActivityLog.objects.filter(created_at__gte=week_ago).count()
    
    # Счет организации
    org_account = OrganizationAccount.get_account()
    
    stats = {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_tickets': total_tickets,
        'new_tickets': new_tickets,
        'recent_activity': recent_activity,
        'recent_logs': recent_logs,
        'org_balance': org_account.balance,
        'org_tax_reserve': org_account.tax_reserve,
    }
    
    blocks = [
        {'title': 'Пользователи и роли', 'desc': 'Создание, редактирование, назначение ролей', 'url': 'admin_users_list', 'icon': '👥'},
        {'title': 'Товары', 'desc': 'Полное управление товарами', 'url': 'admin_products_list', 'icon': '📦'},
        {'title': 'Категории и бренды', 'desc': 'Управление категориями и брендами', 'url': 'admin_categories_list', 'icon': '🏷️'},
        {'title': 'Поставщики', 'desc': 'Управление поставщиками', 'url': 'admin_suppliers_list', 'icon': '🚚'},
        {'title': 'Заказы', 'desc': 'Управление заказами и назначение курьеров', 'url': 'admin_orders_list', 'icon': '📋'},
        {'title': 'Поддержка', 'desc': 'Управление обращениями и назначение ответственных', 'url': 'admin_support_list', 'icon': '💬'},
        {'title': 'Промокоды', 'desc': 'Создание и управление промокодами', 'url': 'admin_promotions_list', 'icon': '🎫'},
        {'title': 'Аналитика и отчёты', 'desc': 'Расширенная аналитика и экспорт данных', 'url': 'admin_analytics', 'icon': '📊'},
        {'title': 'Счет организации', 'desc': 'Управление счетом организации, вывод средств, оплата налогов', 'url': 'admin_org_account', 'icon': '💰'},
        {'title': 'Логи активности', 'desc': 'Просмотр действий пользователей и аудит', 'url': 'admin_activity_logs', 'icon': '📝'},
        {'title': 'Бэкапы БД', 'desc': 'Создание и управление бэкапами базы данных', 'url': 'admin_backups_list', 'icon': '💾'},
    ]
    
    return render(request, 'main/admin/dashboard.html', {
        'blocks': blocks,
        'stats': stats
    })

@login_required
def management_users_list(request):
    if not _user_is_admin(request.user):
        return redirect('profile')
    from django.contrib.auth.models import User as AuthUser
    q = (request.GET.get('q') or '').strip()
    qs = AuthUser.objects.select_related('profile').all().order_by('-date_joined')
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    roles = Role.objects.all().order_by('role_name')
    return render(request, 'main/management/users_list.html', {
        'page_obj': page_obj, 'q': q, 'roles': roles
    })

@login_required
def management_user_edit(request, user_id: int):
    if not _user_is_admin(request.user):
        return redirect('profile')
    from django.contrib.auth.models import User as AuthUser
    from django.contrib.auth.hashers import make_password
    user = get_object_or_404(AuthUser, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if request.method == 'POST':
        # Обновление базовых данных пользователя
        user.username = request.POST.get('username', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        
        # Обновление пароля (если указан)
        new_password = request.POST.get('password', '').strip()
        if new_password:
            user.set_password(new_password)
        
        user.is_active = request.POST.get('is_active') == 'on'
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.is_superuser = request.POST.get('is_superuser') == 'on'
        user.save()
        
        # Обновление профиля
        profile.full_name = request.POST.get('full_name', '').strip()
        profile.phone_number = request.POST.get('phone_number', '').strip()
        birth_date_str = request.POST.get('birth_date', '').strip()
        if birth_date_str:
            try:
                from datetime import datetime
                profile.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        balance_str = request.POST.get('balance', '').strip()
        if balance_str:
            try:
                profile.balance = Decimal(balance_str)
            except (ValueError, InvalidOperation):
                pass
        
        # Обновление секретного слова (только если указано)
        secret_word = request.POST.get('secret_word', '').strip()
        if secret_word:
            profile.secret_word = secret_word
        
        role_id = request.POST.get('role_id')
        if role_id:
            try:
                profile.role = Role.objects.get(pk=role_id)
            except Role.DoesNotExist:
                profile.role = None
        else:
            profile.role = None
        
        old_status = profile.user_status
        profile.user_status = 'blocked' if request.POST.get('blocked') == 'on' else 'active'
        profile.save()
        # Также устанавливаем is_active для дополнительной защиты
        user.is_active = (profile.user_status == 'active')
        user.save()
        if old_status != profile.user_status:
            _log_activity(request.user, 'update', f'user_{user_id}', f'Изменен статус пользователя: {old_status} -> {profile.user_status}', request)
        messages.success(request, 'Пользователь обновлен')
        return redirect('management_users_list')
    roles = Role.objects.all().order_by('role_name')
    return render(request, 'main/management/user_edit.html', {'user_obj': user, 'profile': profile, 'roles': roles})

@login_required
def management_user_toggle_block(request, user_id: int):
    if not _user_is_admin(request.user):
        return redirect('profile')
    from django.contrib.auth.models import User as AuthUser
    user = get_object_or_404(AuthUser, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    old_status = profile.user_status
    profile.user_status = 'active' if profile.user_status == 'blocked' else 'blocked'
    profile.save()
    # Также устанавливаем is_active для дополнительной защиты
    user.is_active = (profile.user_status == 'active')
    user.save()
    _log_activity(request.user, 'update', f'user_{user_id}', f'Изменен статус пользователя: {old_status} -> {profile.user_status}', request)
    messages.success(request, f'Пользователь {"разблокирован" if profile.user_status == "active" else "заблокирован"}')
    return redirect('management_users_list')

@login_required
def management_orders_list(request):
    if not _user_is_admin(request.user):
        return redirect('profile')
    q = (request.GET.get('q') or '').strip()
    qs = Order.objects.select_related('user').all().order_by('-created_at')
    if q:
        qs = qs.filter(Q(id__icontains=q) | Q(user__username__icontains=q) | Q(user__email__icontains=q))
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    return render(request, 'main/management/orders_list.html', {'page_obj': page_obj})

@login_required
def management_order_change_status(request, order_id: int):
    if not _user_is_admin(request.user):
        return redirect('profile')
    order = get_object_or_404(Order, pk=order_id)
    if request.method == 'POST':
        new_status = request.POST.get('order_status')
        if new_status in dict(Order.ORDER_STATUSES):
            order.order_status = new_status
            order.save(update_fields=['order_status'])
            messages.success(request, 'Статус заказа обновлен')
    return redirect('management_orders_list')

@login_required
def management_analytics_export_csv(request):
    if not _user_is_admin(request.user):
        return redirect('profile')
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['OrderID', 'User', 'Amount', 'Status', 'Created'])
    for o in Order.objects.select_related('user').all().order_by('-created_at')[:1000]:
        writer.writerow([o.id, o.user.username if o.user else '', o.total_amount, o.order_status, o.created_at.strftime('%Y-%m-%d %H:%M')])
    return response

# ========== Управление промокодами ==========
@login_required
def management_promotions_list(request):
    if not _user_is_admin(request.user):
        return redirect('profile')
    q = (request.GET.get('q') or '').strip()
    qs = Promotion.objects.all().order_by('-start_date', 'promo_code')
    if q:
        qs = qs.filter(Q(promo_code__icontains=q) | Q(promo_description__icontains=q))
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    return render(request, 'main/management/promotions_list.html', {'page_obj': page_obj, 'q': q})

@login_required
def management_promotion_add(request):
    if not _user_is_admin(request.user):
        return redirect('profile')
    if request.method == 'POST':
        promo_code = request.POST.get('promo_code', '').strip().upper()
        promo_description = request.POST.get('promo_description', '').strip()
        discount_str = request.POST.get('discount', '').strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not promo_code:
            messages.error(request, 'Код промокода обязателен')
            return redirect('management_promotion_add')
        
        try:
            discount = Decimal(discount_str) if discount_str else Decimal('0')
        except (ValueError, InvalidOperation):
            discount = Decimal('0')
        
        start_date = None
        end_date = None
        if start_date_str:
            try:
                from datetime import datetime
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_date_str:
            try:
                from datetime import datetime
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        Promotion.objects.create(
            promo_code=promo_code,
            promo_description=promo_description,
            discount=discount,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active
        )
        messages.success(request, 'Промокод создан')
        return redirect('management_promotions_list')
    return render(request, 'main/management/promotion_edit.html', {'promotion': None})

@login_required
def management_promotion_edit(request, promo_id: int):
    if not _user_is_admin(request.user):
        return redirect('profile')
    promotion = get_object_or_404(Promotion, pk=promo_id)
    if request.method == 'POST':
        promotion.promo_code = request.POST.get('promo_code', '').strip().upper()
        promotion.promo_description = request.POST.get('promo_description', '').strip()
        discount_str = request.POST.get('discount', '').strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        promotion.is_active = request.POST.get('is_active') == 'on'
        
        try:
            promotion.discount = Decimal(discount_str) if discount_str else Decimal('0')
        except (ValueError, InvalidOperation):
            pass
        
        promotion.start_date = None
        promotion.end_date = None
        if start_date_str:
            try:
                from datetime import datetime
                promotion.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_date_str:
            try:
                from datetime import datetime
                promotion.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        promotion.save()
        messages.success(request, 'Промокод обновлен')
        return redirect('management_promotions_list')
    return render(request, 'main/management/promotion_edit.html', {'promotion': promotion})

@login_required
def management_promotion_delete(request, promo_id: int):
    if not _user_is_admin(request.user):
        return redirect('profile')
    promotion = get_object_or_404(Promotion, pk=promo_id)
    if request.method == 'POST':
        promotion.delete()
        messages.success(request, 'Промокод удален')
        return redirect('management_promotions_list')
    return render(request, 'main/management/promotion_delete.html', {'promotion': promotion})
@login_required
def receipts_list(request):
    receipts = Receipt.objects.filter(user=request.user).select_related('order').order_by('-created_at')
    return render(request, 'profile/receipts.html', {'receipts': receipts})

@login_required
@require_POST
def validate_promo(request):
    """AJAX: проверить промокод и вернуть сумму скидки и итоги"""
    code = (request.POST.get('promo_code') or '').strip().upper()
    if not code:
        return JsonResponse({'success': False, 'message': 'Укажите промокод'}, status=400)
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        return JsonResponse({'success': False, 'message': 'Корзина пуста'}, status=400)
    try:
        promo = Promotion.objects.get(promo_code=code)
        # Проверяем активность промокода
        if not promo.is_active:
            return JsonResponse({'success': False, 'message': 'Промокод неактивен'}, status=400)
        from django.utils import timezone
        today = timezone.now().date()
        if promo.start_date and promo.start_date > today:
            return JsonResponse({'success': False, 'message': 'Промокод еще не действует'}, status=400)
        if promo.end_date and promo.end_date < today:
            return JsonResponse({'success': False, 'message': 'Промокод истек'}, status=400)
        cart_total = cart.total_price()
        delivery_cost = Decimal('1000.00')
        discount_amount = (cart_total * (promo.discount / Decimal('100'))).quantize(Decimal('0.01'))
        subtotal_after_discount = cart_total - discount_amount
        pre_vat = subtotal_after_discount + delivery_cost  # Товары - скидка + доставка
        vat_rate = Decimal('20.00')
        vat_amount = (pre_vat * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
        total = (pre_vat + vat_amount).quantize(Decimal('0.01'))
        return JsonResponse({
            'success': True,
            'promo': {'code': promo.promo_code, 'discount_percent': str(promo.discount)},
            'amounts': {
                'subtotal': float(cart_total),
                'discount': float(discount_amount),
                'delivery': float(delivery_cost),
                'vat': float(vat_amount),
                'total': float(total)
            }
        })
    except Promotion.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Неверный промокод'}, status=404)

@login_required
def receipt_pdf(request, receipt_id: int):
    receipt = get_object_or_404(Receipt, id=receipt_id, user=request.user)
    config = ReceiptConfig.objects.first() or ReceiptConfig.objects.create()

    # Генерируем PDF через reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import black
        import io

        # Создаем буфер для PDF
        buffer = io.BytesIO()

        # Создаем PDF canvas
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Используем TTF шрифт с поддержкой кириллицы
        # Пытаемся использовать системные шрифты Windows или загрузить TTF
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"
        
        # Пытаемся использовать системные шрифты с поддержкой кириллицы
        try:
            import platform
            import os
            
            system = platform.system()
            arial_found = False
            
            # Для Windows используем системные шрифты
            if system == 'Windows':
                font_dir = r'C:\Windows\Fonts'
                
                # Список возможных путей к Arial (разные версии Windows могут иметь разные имена)
                arial_variants = [
                    'arial.ttf',
                    'Arial.ttf',
                    'ARIAL.TTF',
                    'arialuni.ttf',  # Arial Unicode MS (полная поддержка Unicode)
                ]
                
                arial_bold_variants = [
                    'arialbd.ttf',
                    'Arialbd.ttf',
                    'ARIALBD.TTF',
                    'arialbi.ttf',  # Arial Bold Italic
                ]
                
                # Пробуем найти и зарегистрировать Arial
                for variant in arial_variants:
                    arial_path = os.path.join(font_dir, variant)
                    if os.path.exists(arial_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Arial', arial_path))
                            font_name = 'Arial'
                            arial_found = True
                            break
                        except Exception:
                            continue
                
                # Пробуем найти и зарегистрировать Arial Bold
                if arial_found:
                    for variant in arial_bold_variants:
                        arial_bold_path = os.path.join(font_dir, variant)
                        if os.path.exists(arial_bold_path):
                            try:
                                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                                font_bold = 'Arial-Bold'
                                break
                            except Exception:
                                pass
                    # Если не нашли жирный, используем обычный Arial
                    if font_bold == 'Helvetica-Bold':
                        font_bold = 'Arial'
            
            # Для Linux пробуем использовать системные шрифты
            elif system == 'Linux':
                font_dirs = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                    '/usr/share/fonts/TTF/DejaVuSans.ttf',
                ]
                for font_path in font_dirs:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                            font_name = 'DejaVu'
                            font_bold = 'DejaVu'
                            arial_found = True
                            break
                        except Exception:
                            continue
            
            # Для macOS пробуем использовать системные шрифты
            elif system == 'Darwin':
                font_dirs = [
                    '/System/Library/Fonts/Helvetica.ttc',
                    '/Library/Fonts/Arial.ttf',
                ]
                for font_path in font_dirs:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Arial', font_path))
                            font_name = 'Arial'
                            font_bold = 'Arial'
                            arial_found = True
                            break
                        except Exception:
                            continue
                            
        except Exception as e:
            # Если не получилось, используем стандартные шрифты
            # В этом случае кириллица может не отображаться
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось загрузить шрифт с поддержкой кириллицы: {e}")

        y = height - 20 * mm
        line_height = 6 * mm
        left_margin = 15 * mm

        def draw(text: str, bold: bool = False, font_size: int = 10):
            nonlocal y
            try:
                # Преобразуем текст в строку и убеждаемся что это Unicode
                text_str = str(text)
                # Используем drawString - в reportlab 4.x он поддерживает Unicode
                c.setFont(font_bold if bold else font_name, font_size)
                # Проверяем длину строки и разбиваем если нужно
                max_width = width - (left_margin * 2)
                # Простая проверка - если текст слишком длинный, обрезаем
                if len(text_str) > 80:
                    text_str = text_str[:77] + "..."
                c.drawString(left_margin, y, text_str)
                y -= line_height
            except UnicodeEncodeError:
                # Если проблема с кодировкой, пробуем транслитерацию
                try:
                    text_str = str(text).encode('ascii', 'ignore').decode('ascii')
                    c.setFont(font_name, font_size)
                    c.drawString(left_margin, y, text_str)
                    y -= line_height
                except:
                    # В крайнем случае просто пропускаем проблемные символы
                    c.setFont(font_name, font_size)
                    c.drawString(left_margin, y, "?")
                    y -= line_height
            except Exception as e:
                # Общая обработка ошибок
                c.setFont(font_name, font_size)
                c.drawString(left_margin, y, str(text)[:50])
            y -= line_height

        # Заголовок
        draw(str(config.company_name or "Магазин"), bold=True, font_size=14)
        draw(f"ИНН: {str(config.company_inn or '')}")
        draw(f"Адрес: {str(config.company_address or '')}")
        draw(f"Кассир: {str(config.cashier_name or '')}")
        draw(f"Смена № {str(config.shift_number or '')}")
        
        y -= 3 * mm
        draw("─" * 50)
        y -= 2 * mm
        
        draw(f"Чек № {receipt.number or receipt.id}", bold=True)
        draw(f"Дата: {receipt.created_at.strftime('%d.%m.%Y')}")
        draw(f"Время: {receipt.created_at.strftime('%H:%M')}")

        y -= 3 * mm
        draw("Товары:", bold=True)
        draw("─" * 50)

        # Товары
        for item in receipt.items.all():
            product_name = str(item.product_name or 'Товар')
            # Обрезаем длинные названия
            if len(product_name) > 40:
                product_name = product_name[:37] + "..."
            
            draw(f"{product_name}")
            draw(f"  {item.quantity} шт. x {item.unit_price} ₽ = {item.line_total} ₽")
            if item.vat_amount:
                draw(f"  НДС {receipt.vat_rate}%: {item.vat_amount} ₽")
        y -= 2 * mm

        y -= 2 * mm
        draw("─" * 50)
        
        # Показываем промокод, если есть
        if receipt.order and receipt.order.promo_code:
            draw(f"Промокод: {receipt.order.promo_code.promo_code} (-{receipt.discount_amount} ₽)", bold=True)
            y -= 2 * mm
        
        # Показываем суммы
        if receipt.subtotal:
            draw(f"Товары: {receipt.subtotal} ₽")
        if receipt.delivery_cost:
            draw(f"Доставка: {receipt.delivery_cost} ₽")
        if receipt.discount_amount:
            draw(f"Скидка: -{receipt.discount_amount} ₽")
        
        draw("─" * 50)
        draw(f"Итого: {receipt.total_amount} ₽", bold=True, font_size=12)
        draw(f"В том числе НДС {receipt.vat_rate}%: {receipt.vat_amount} ₽")
        
        y -= 3 * mm
        payment_label = "Наличные" if receipt.payment_method == 'cash' else ("С баланса" if receipt.payment_method == 'balance' else "Банковская карта")
        draw("Оплата:", bold=True)
        draw(f"{payment_label}: {receipt.total_amount} ₽")

        y -= 3 * mm
        draw("Спасибо за покупку!", bold=True)
        
        if config.site_fns:
            draw(f"Сайт ФНС: {str(config.site_fns)}")
        if config.kkt_rn:
            draw(f"РН ККТ: {str(config.kkt_rn)}")
        if config.kkt_sn:
            draw(f"ЗН ККТ: {str(config.kkt_sn)}")
        if config.fn_number:
            draw(f"ФН: {str(config.fn_number)}")

        # Завершаем страницу
        c.showPage()
        c.save()
        
        # Получаем PDF из буфера
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()

        # Создаем HTTP ответ с правильными заголовками
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"receipt_{receipt.id}.pdf"
        # Используем inline для просмотра в браузере, attachment для скачивания
        # Можно добавить параметр ?download=1 для принудительного скачивания
        if request.GET.get('download') == '1':
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except ImportError:
        # Если reportlab не установлен
        from django.contrib import messages
        messages.error(request, "PDF генератор не установлен. Пожалуйста, установите reportlab.")
        return redirect('receipts_list')
    except Exception as e:
        # Логируем ошибку для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка генерации PDF: {str(e)}")
        
        # Fallback: возвращаем HTML с возможностью печати
        html = render_to_string('profile/receipt_fallback.html', {
            'receipt': receipt,
            'config': config,
        })
        response = HttpResponse(html, content_type='text/html')
        return response


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart.html', {'cart': cart})


@login_required
def add_to_cart(request, product_id):
    if request.method == "POST":
        product = get_object_or_404(Product, id=product_id)
        
        # Пытаемся получить данные из JSON (для AJAX запросов)
        try:
            data = json.loads(request.body)
            size_id = data.get("size_id")
            quantity = int(data.get("quantity", 1))
        except (json.JSONDecodeError, ValueError):
            # Если не JSON, пытаемся получить из POST
            size_id = request.POST.get('size_id')
            quantity = int(request.POST.get('quantity', 1))

        size = None
        if size_id:
            try:
                size = ProductSize.objects.get(id=size_id, product=product)
            except ProductSize.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Размер не найден'}, status=400)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        # Проверяем, есть ли уже такой товар с этим размером
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
            defaults={'unit_price': product.final_price, 'quantity': quantity}
        )

        if not created:
            item.quantity += quantity
            item.save()

        return JsonResponse({
            'success': True, 
            'cart_count': cart.items.count(),
            'product': {
                'id': product.id,
                'name': product.product_name,
                'size': size.size_label if size else None,
                'price': str(product.final_price)
            }
        })
    
    return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('cart')


@login_required
def update_cart_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    new_qty = int(request.POST.get('quantity', 1))
    
    # Проверка количества на складе
    if item.size:
        if item.size.size_stock < new_qty:
            error_msg = f'Недостаточно товара на складе. Доступно: {item.size.size_stock}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'message': error_msg
                }, status=400)
            messages.error(request, error_msg)
            return redirect('cart')
    elif item.product.stock_quantity < new_qty:
        error_msg = f'Недостаточно товара на складе. Доступно: {item.product.stock_quantity}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'message': error_msg
            }, status=400)
        messages.error(request, error_msg)
        return redirect('cart')
    
    item.quantity = new_qty
    item.save()
    
    # Если это AJAX запрос, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'subtotal': float(item.subtotal()), 
            'total': float(item.cart.total_price())
        })
    
    # Иначе редирект
    messages.success(request, "Количество обновлено.")
    return redirect('cart')

@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        messages.warning(request, "Ваша корзина пуста.")
        return redirect('cart')

    # Если форма оформления заказа отправлена
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        saved_payment_id = request.POST.get('saved_payment_id')
        promo_code = request.POST.get('promo_code', '').strip()
        
        # Данные новой карты (если не используется сохраненная)
        card_number = request.POST.get('card_number', '').strip()
        card_holder_name = request.POST.get('card_holder_name', '').strip()
        expiry_month = request.POST.get('expiry_month', '').strip()
        expiry_year = request.POST.get('expiry_year', '').strip()
        save_card = request.POST.get('save_card') == 'on'

        if not address_id:
            messages.error(request, "Пожалуйста, выберите адрес доставки.")
            return redirect('checkout')

        # Проверка количества товара на складе
        errors = []
        for item in cart.items.all():
            if item.size:
                if item.size.size_stock < item.quantity:
                    errors.append(f"Товар '{item.product.product_name}' размера {item.size.size_label}: недостаточно на складе (доступно: {item.size.size_stock}, запрошено: {item.quantity})")
            elif item.product.stock_quantity < item.quantity:
                errors.append(f"Товар '{item.product.product_name}': недостаточно на складе (доступно: {item.product.stock_quantity}, запрошено: {item.quantity})")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('checkout')

        # Проверка промокода
        promo = None
        discount_amount = Decimal('0')
        if promo_code:
            try:
                promo = Promotion.objects.get(promo_code=promo_code.upper(), is_active=True)
                # Проверяем даты действия промокода
                from django.utils import timezone
                today = timezone.now().date()
                if promo.start_date and promo.start_date > today:
                    messages.error(request, "Промокод еще не действует.")
                    return redirect('checkout')
                if promo.end_date and promo.end_date < today:
                    messages.error(request, "Промокод истек.")
                    return redirect('checkout')
                # Вычисляем скидку
                cart_total = cart.total_price()
                discount_amount = cart_total * (promo.discount / Decimal('100'))
            except Promotion.DoesNotExist:
                messages.error(request, "Неверный промокод.")
                return redirect('checkout')

        address = UserAddress.objects.get(id=address_id, user=request.user)
        
        # Вычисляем итоговую сумму с учетом скидки и доставки
        cart_total = cart.total_price()
        delivery_cost = Decimal('1000.00')  # Доставка всегда 1000 рублей
        subtotal_after_discount = cart_total - discount_amount
        pre_vat_amount = subtotal_after_discount + delivery_cost  # Сумма товаров + доставка
        vat_rate = Decimal('20.00')
        vat_amount = (pre_vat_amount * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
        
        # Налог на прибыль 13% рассчитывается с суммы после НДС
        amount_after_vat = pre_vat_amount + vat_amount
        tax_rate = Decimal('13.00')
        tax_amount = (amount_after_vat * tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        
        final_amount = amount_after_vat.quantize(Decimal('0.01'))

        # Проверяем способ оплаты
        payment_method = request.POST.get('payment_method', 'cash')  # cash, card или balance
        paid_from_balance = False
        
        # Если оплата с баланса
        if payment_method == 'balance':
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if profile.balance < final_amount:
                messages.error(request, f"Недостаточно средств на балансе. Текущий баланс: {profile.balance} ₽, требуется: {final_amount} ₽")
                return redirect('checkout')
            paid_from_balance = True

        # Вся логика оформления в транзакции
        with transaction.atomic():
            # Создаем заказ
            order = Order.objects.create(
                user=request.user,
                address=address,
                total_amount=final_amount,
                delivery_cost=delivery_cost,
                promo_code=promo,
                discount_amount=discount_amount,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                paid_from_balance=paid_from_balance,
                order_status='paid' if paid_from_balance else 'processing'
            )

            # Обработка способа оплаты
            saved_payment = None
            payment_method_type = 'cash'
            payment_status = 'pending'
            
            if payment_method == 'cash':
                payment_method_type = 'cash'
                payment_status = 'pending'
            elif payment_method == 'balance':
                payment_method_type = 'balance'
                payment_status = 'paid'
                
                # Списываем с баланса
                profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
                if profile.balance < final_amount:
                    order.delete()
                    messages.error(request, f"Недостаточно средств на балансе. Текущий баланс: {profile.balance} ₽, требуется: {final_amount} ₽")
                    return redirect('checkout')
                balance_before = profile.balance
                profile.balance -= final_amount
                profile.save()
                
                # Создаем транзакцию
                BalanceTransaction.objects.create(
                    user=request.user,
                    transaction_type='order_payment',
                    amount=final_amount,
                    balance_before=balance_before,
                    balance_after=profile.balance,
                    description=f'Оплата заказа #{order.id}',
                    order=order,
                    status='completed'
                )
            elif payment_method == 'card':
                payment_status = 'paid'
                # Используем сохраненную карту
                if saved_payment_id and saved_payment_id != '':
                    saved_payment = SavedPaymentMethod.objects.select_for_update().get(id=saved_payment_id, user=request.user)
                    payment_method_type = saved_payment.card_type or 'card'
                    if saved_payment.balance < final_amount:
                        order.delete()
                        messages.error(request, f"Недостаточно средств на выбранной карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽")
                        return redirect('checkout')
                    # Списываем (проверяем, что баланс не станет отрицательным)
                    new_card_balance = saved_payment.balance - final_amount
                    if new_card_balance < 0:
                        order.delete()
                        messages.error(request, f"Недостаточно средств на выбранной карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽")
                        return redirect('checkout')
                    saved_payment.balance = new_card_balance
                    saved_payment.save()
                    # Фиксируем транзакцию по карте
                    CardTransaction.objects.create(
                        saved_payment_method=saved_payment,
                        transaction_type='withdrawal',
                        amount=final_amount,
                        description=f'Оплата заказа #{order.id}',
                        status='completed'
                    )
                # Новая карта: разрешаем только если карта будет сохранена и на ней достаточно средств
                elif card_number and card_holder_name and expiry_month and expiry_year:
                    payment_method_type = 'visa' if card_number.startswith('4') else 'mastercard' if card_number.startswith('5') else 'card'
                    if save_card:
                        card_type = payment_method_type
                        card_last_4 = card_number[-4:] if len(card_number) >= 4 else card_number
                        is_default = not SavedPaymentMethod.objects.filter(user=request.user).exists()
                        saved_payment = SavedPaymentMethod.objects.create(
                            user=request.user,
                            card_number=card_last_4,
                            card_holder_name=card_holder_name,
                            expiry_month=expiry_month,
                            expiry_year=expiry_year,
                            card_type=card_type,
                            is_default=is_default
                        )
                        if saved_payment.balance < final_amount:
                            order.delete()
                            messages.error(request, f"Недостаточно средств на карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽")
                            return redirect('checkout')
                        # Списываем (проверяем, что баланс не станет отрицательным)
                        new_card_balance = saved_payment.balance - final_amount
                        if new_card_balance < 0:
                            order.delete()
                            messages.error(request, f"Недостаточно средств на карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽")
                            return redirect('checkout')
                        saved_payment.balance = new_card_balance
                        saved_payment.save()
                        CardTransaction.objects.create(
                            saved_payment_method=saved_payment,
                            transaction_type='withdrawal',
                            amount=final_amount,
                            description=f'Оплата заказа #{order.id}',
                            status='completed'
                        )
                    else:
                        order.delete()
                        messages.error(request, "Для оплаты новой картой сначала сохраните карту и убедитесь в наличии средств.")
                        return redirect('checkout')
                else:
                    order.delete()
                    messages.error(request, "Пожалуйста, выберите или введите данные карты.")
                    return redirect('checkout')
            
            # Создаем запись о платеже
            payment = Payment.objects.create(
                order=order,
                payment_method=payment_method_type,
                payment_amount=final_amount,
                payment_status=payment_status,
                saved_payment_method=saved_payment,
                promo_code=promo
            )

            # Если платеж прошел (balance или card), переводим заказ в 'paid'
            if payment_status == 'paid' and order.order_status != 'paid':
                order.order_status = 'paid'
                order.save(update_fields=['order_status'])
            
            # Переводим средства на счет организации (если платеж прошел, но не наличными)
            # Наличные оплачиваются при получении, поэтому средства переводятся позже
            if payment_status == 'paid' and payment_method != 'cash':
                org_account = OrganizationAccount.get_account()
                balance_before = org_account.balance
                tax_reserve_before = org_account.tax_reserve
                
                # Зачисляем сумму заказа на счет организации
                org_account.balance += final_amount
                
                # Резервируем налог 13% от суммы заказа
                org_account.tax_reserve += tax_amount
                
                org_account.save()
                
                # Создаем транзакцию
                OrganizationTransaction.objects.create(
                    organization_account=org_account,
                    transaction_type='order_payment',
                    amount=final_amount,
                    description=f'Поступление от заказа #{order.id}',
                    order=order,
                    created_by=request.user,
                    balance_before=balance_before,
                    balance_after=org_account.balance,
                    tax_reserve_before=tax_reserve_before,
                    tax_reserve_after=org_account.tax_reserve
                )

            # Создаем позиции заказа и вычитаем количество со склада
            order_items = list(cart.items.all())
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    size=item.size,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                
                # Вычитаем количество со склада
                if item.size:
                    # блокировка на уровне ORM отсутствует, полагаемся на транзакцию
                    item.size.size_stock -= item.quantity
                    item.size.save()
                    item.product.stock_quantity -= item.quantity
                    item.product.save()
                else:
                    item.product.stock_quantity -= item.quantity
                    item.product.save()
            
            cart.items.all().delete()

            # Формируем чек
            receipt_subtotal = Decimal('0.00')
            receipt_vat_total = Decimal('0.00')
            
            # Рассчитываем НДС для доставки
            delivery_vat = (delivery_cost * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
            
            receipt = Receipt.objects.create(
                user=request.user,
                order=order,
                status='executed',
                total_amount=final_amount,
                subtotal=cart_total,
                delivery_cost=delivery_cost,
                discount_amount=discount_amount,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                payment_method=payment_method if payment_method in ['cash', 'balance', 'card'] else 'card'
            )
            
            # Добавляем товары в чек
            for item in order.items.select_related('product').all():
                line_total = (item.unit_price * item.quantity).quantize(Decimal('0.01'))
                line_vat = (line_total * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
                ReceiptItem.objects.create(
                    receipt=receipt,
                    product_name=item.product.product_name if item.product else 'Товар',
                    article=str(item.product.id if item.product else ''),
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=line_total,
                    vat_amount=line_vat
                )
                receipt_subtotal += line_total
                receipt_vat_total += line_vat
            
            # Добавляем доставку как отдельную позицию в чек
            ReceiptItem.objects.create(
                receipt=receipt,
                product_name='Доставка',
                article='DELIVERY',
                quantity=1,
                unit_price=delivery_cost,
                line_total=delivery_cost,
                vat_amount=delivery_vat
            )
            receipt_vat_total += delivery_vat
            
            # Обновляем итоговые суммы в чеке
            receipt.total_amount = final_amount.quantize(Decimal('0.01'))
            receipt.vat_amount = receipt_vat_total.quantize(Decimal('0.01'))
            receipt.save()
            _log_activity(request.user, 'create', f'order_{order.id}', f'Создан заказ на сумму {final_amount} ₽', request)
        messages.success(request, "Заказ успешно оформлен!")
        return redirect('order_detail', pk=order.pk)

    # GET запрос - показываем форму
    addresses = UserAddress.objects.filter(user=request.user)
    saved_payments = SavedPaymentMethod.objects.filter(user=request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Рассчитываем суммы для отображения
    cart_total = cart.total_price()
    delivery_cost = Decimal('1000.00')
    vat_rate = Decimal('20.00')
    # НДС рассчитывается с суммы товаров + доставка
    pre_vat_amount = cart_total + delivery_cost
    vat_amount = (pre_vat_amount * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
    total_with_vat = pre_vat_amount + vat_amount
    
    return render(request, 'checkout.html', {
        'cart': cart,
        'addresses': addresses,
        'saved_payments': saved_payments,
        'user_balance': profile.balance,
        'delivery_cost': delivery_cost,
        'vat_rate': vat_rate,
        'vat_amount': vat_amount,
        'total_with_vat': total_with_vat,
        'subtotal': cart_total
    })

@login_required
def update_cart_size(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if request.method == 'POST':
        size_id = request.POST.get('size_id')
        new_size = get_object_or_404(ProductSize, id=size_id, product=item.product)
        item.size = new_size
        item.save()
    return redirect('cart')

# =================== Отзывы на товары ===================
@login_required
@require_POST
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    data = json.loads(request.body)
    rating = int(data.get('rating', 0))
    review_text = data.get('review_text', '').strip()
    
    if not 1 <= rating <= 5:
        return JsonResponse({'success': False, 'message': 'Оценка должна быть от 1 до 5'}, status=400)
    
    # Фильтруем нецензурную лексику
    from .utils import filter_profanity
    review_text = filter_profanity(review_text)
    
    # Проверяем, купил ли пользователь этот товар
    user_has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        product=product
    ).annotate(
        has_paid=Exists(
            Payment.objects.filter(order=OuterRef('order'), payment_status='paid')
        )
    ).filter(
        Q(has_paid=True) |
        Q(order__order_status__in=['paid', 'shipped', 'delivered'])
    ).exists()
    
    if not user_has_purchased:
        return JsonResponse({'success': False, 'message': 'Вы можете оставить отзыв только на купленный товар'}, status=403)
    
    # Проверяем, не оставлял ли пользователь уже отзыв на этот товар
    existing_review = ProductReview.objects.filter(user=request.user, product=product).first()
    if existing_review:
        existing_review.rating_value = rating
        existing_review.review_text = review_text
        existing_review.save()
        return JsonResponse({'success': True, 'message': 'Отзыв обновлен'})
    
    ProductReview.objects.create(
        user=request.user,
        product=product,
        rating_value=rating,
        review_text=review_text
    )
    return JsonResponse({'success': True, 'message': 'Отзыв добавлен'})

def get_product_reviews(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = ProductReview.objects.filter(product=product).select_related('user').order_by('-created_at')
    
    # Ограничиваем количество отзывов для модального окна
    limit = int(request.GET.get('limit', 2))
    reviews_limited = reviews[:limit]
    
    reviews_data = []
    for review in reviews_limited:
        reviews_data.append({
            'id': review.id,
            'user_name': review.user.get_full_name() or review.user.username if review.user else 'Анонимный пользователь',
            'rating': review.rating_value,
            'text': review.review_text or '',
            'created_at': review.created_at.strftime('%d.%m.%Y %H:%M')
        })
    
    # Средний рейтинг
    avg_rating = reviews.aggregate(avg=Avg('rating_value'))['avg'] or 0
    total_reviews = reviews.count()
    
    # Можно ли пользователю оставить отзыв (для модального окна)
    user_can_review = False
    if request.user.is_authenticated:
        user_can_review = OrderItem.objects.filter(
            order__user=request.user,
            product=product
        ).annotate(
            has_paid=Exists(
                Payment.objects.filter(order=OuterRef('order'), payment_status='paid')
            )
        ).filter(
            Q(has_paid=True) |
            Q(order__order_status__in=['paid', 'shipped', 'delivered'])
        ).exists()
    
    return JsonResponse({
        'success': True,
        'reviews': reviews_data,
        'avg_rating': round(avg_rating, 1),
        'total_reviews': total_reviews,
        'has_more': total_reviews > limit,
        'user_can_review': user_can_review
    })

@login_required
def product_reviews_page(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = ProductReview.objects.filter(product=product).select_related('user').order_by('-created_at')
    
    # Проверяем, купил ли пользователь этот товар
    user_has_purchased = False
    if request.user.is_authenticated:
        user_has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            product=product
        ).annotate(
            has_paid=Exists(
                Payment.objects.filter(order=OuterRef('order'), payment_status='paid')
            )
        ).filter(
            Q(has_paid=True) |
            Q(order__order_status__in=['paid', 'shipped', 'delivered'])
        ).exists()
    
    # Средний рейтинг
    avg_rating = reviews.aggregate(avg=Avg('rating_value'))['avg'] or 0
    total_reviews = reviews.count()
    
    # Проверяем, оставлял ли пользователь уже отзыв
    user_review = None
    if request.user.is_authenticated:
        user_review = ProductReview.objects.filter(user=request.user, product=product).first()
    
    return render(request, 'product_reviews.html', {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'total_reviews': total_reviews,
        'user_has_purchased': user_has_purchased,
        'user_review': user_review
    })

# =================== Техническая поддержка ===================
@login_required
def support_view(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support.html', {'tickets': tickets})

@login_required
def create_support_ticket(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        subject = data.get('subject', '').strip()
        message_text = data.get('message_text', '').strip()
        
        if not subject or not message_text:
            return JsonResponse({'success': False, 'message': 'Заполните все поля'}, status=400)
        
        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            message_text=message_text,
            ticket_status='new'
        )
        
        _log_activity(request.user, 'create', f'ticket_{ticket.id}', f'Создано обращение в поддержку: {subject}', request)
        
        return JsonResponse({
            'success': True,
            'message': 'Обращение создано',
            'ticket_id': ticket.id
        })
    
    return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)

@login_required
def support_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    return render(request, 'support_detail.html', {'ticket': ticket})

# =================== ПАНЕЛЬ МЕНЕДЖЕРА ===================

@login_required
def manager_dashboard(request):
    """Главная панель менеджера"""
    if not _user_is_manager(request.user):
        messages.error(request, "Доступ запрещен. Требуется роль менеджера.")
        return redirect('profile')
    
    # Статистика для дашборда
    from django.db.models import Count, Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    
    total_products = Product.objects.count()
    available_products = Product.objects.filter(is_available=True).count()
    total_orders = Order.objects.count()
    orders_today = Order.objects.filter(created_at__date=timezone.now().date()).count()
    total_users = User.objects.count()
    active_users = UserProfile.objects.filter(user_status='active').count()
    new_tickets = SupportTicket.objects.filter(ticket_status='new').count()
    
    # Популярные товары за последний месяц
    month_ago = timezone.now() - timedelta(days=30)
    popular_products = Product.objects.filter(
        orderitem__order__created_at__gte=month_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]
    
    stats = {
        'total_products': total_products,
        'available_products': available_products,
        'total_orders': total_orders,
        'orders_today': orders_today,
        'total_users': total_users,
        'active_users': active_users,
        'new_tickets': new_tickets,
        'popular_products': popular_products,
    }
    
    blocks = [
        {'title': 'Управление товарами', 'desc': 'Добавление, редактирование и удаление товаров', 'url': 'manager_products_list', 'icon': '📦'},
        {'title': 'Категории и бренды', 'desc': 'Управление категориями и брендами', 'url': 'manager_categories_list', 'icon': '🏷️'},
        {'title': 'Заказы', 'desc': 'Просмотр и управление заказами', 'url': 'manager_orders_list', 'icon': '📋'},
        {'title': 'Пользователи', 'desc': 'Просмотр и управление пользователями', 'url': 'manager_users_list', 'icon': '👥'},
        {'title': 'Поддержка', 'desc': 'Обработка обращений в поддержку', 'url': 'manager_support_list', 'icon': '💬'},
        {'title': 'Аналитика', 'desc': 'Статистика и отчёты', 'url': 'manager_analytics', 'icon': '📊'},
    ]
    
    return render(request, 'main/manager/dashboard.html', {
        'blocks': blocks,
        'stats': stats
    })

# =================== УПРАВЛЕНИЕ ТОВАРАМИ ===================

@login_required
def manager_products_list(request):
    """Список товаров для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    q = (request.GET.get('q') or '').strip()
    category_id = request.GET.get('category')
    brand_id = request.GET.get('brand')
    available_filter = request.GET.get('available')
    
    qs = Product.objects.select_related('category', 'brand').prefetch_related('sizes', 'producttag_set__tag').all()
    
    if q:
        qs = qs.filter(Q(product_name__icontains=q) | Q(product_description__icontains=q))
    if category_id:
        qs = qs.filter(category_id=category_id)
    if brand_id:
        qs = qs.filter(brand_id=brand_id)
    if available_filter == 'yes':
        qs = qs.filter(is_available=True)
    elif available_filter == 'no':
        qs = qs.filter(is_available=False)
    
    qs = qs.order_by('-added_at')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    return render(request, 'main/manager/products_list.html', {
        'page_obj': page_obj,
        'q': q,
        'categories': categories,
        'brands': brands,
        'category_id': category_id,
        'brand_id': brand_id,
        'available_filter': available_filter
    })

@login_required
def manager_product_add(request):
    """Добавление товара"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    suppliers = Supplier.objects.all()
    tags = Tag.objects.all()
    
    if request.method == 'POST':
        try:
            stock_qty = int(request.POST.get('stock_quantity', '0'))
            is_available_param = request.POST.get('is_available') == 'on'
            # Автоматически отключаем товар, если остаток 0
            if stock_qty <= 0:
                is_available_param = False
            
            product = Product.objects.create(
                product_name=request.POST.get('product_name', '').strip(),
                product_description=request.POST.get('product_description', '').strip(),
                price=Decimal(request.POST.get('price', '0')),
                discount=Decimal(request.POST.get('discount', '0')),
                stock_quantity=stock_qty,
                category_id=request.POST.get('category_id') or None,
                brand_id=request.POST.get('brand_id') or None,
                supplier_id=request.POST.get('supplier_id') or None,
                main_image_url=request.POST.get('main_image_url', '').strip() or None,
                image_url_1=request.POST.get('image_url_1', '').strip() or None,
                image_url_2=request.POST.get('image_url_2', '').strip() or None,
                image_url_3=request.POST.get('image_url_3', '').strip() or None,
                image_url_4=request.POST.get('image_url_4', '').strip() or None,
                is_available=is_available_param
            )
            
            # Добавляем размеры
            size_labels = request.POST.getlist('size_label')
            size_stocks = request.POST.getlist('size_stock')
            for label, stock in zip(size_labels, size_stocks):
                if label.strip():
                    ProductSize.objects.create(
                        product=product,
                        size_label=label.strip(),
                        size_stock=int(stock or '0')
                    )
            
            # Добавляем теги
            tag_ids = request.POST.getlist('tags')
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.get_or_create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass
            
            _log_activity(request.user, 'create', f'product_{product.id}', f'Создан товар: {product.product_name}', request)
            messages.success(request, 'Товар успешно добавлен')
            return redirect('manager_products_list')
        except Exception as e:
            messages.error(request, f'Ошибка при добавлении товара: {str(e)}')
    
    return render(request, 'main/manager/product_edit.html', {
        'product': None,
        'categories': categories,
        'brands': brands,
        'suppliers': suppliers,
        'tags': tags
    })

@login_required
def manager_product_edit(request, product_id):
    """Редактирование товара"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    product = get_object_or_404(Product, pk=product_id)
    categories = Category.objects.all()
    brands = Brand.objects.all()
    suppliers = Supplier.objects.all()
    tags = Tag.objects.all()
    product_tags = [pt.tag.id for pt in product.producttag_set.all()]
    
    if request.method == 'POST':
        try:
            product.product_name = request.POST.get('product_name', '').strip()
            product.product_description = request.POST.get('product_description', '').strip()
            product.price = Decimal(request.POST.get('price', '0'))
            product.discount = Decimal(request.POST.get('discount', '0'))
            stock_qty = int(request.POST.get('stock_quantity', '0'))
            product.stock_quantity = stock_qty
            product.category_id = request.POST.get('category_id') or None
            product.brand_id = request.POST.get('brand_id') or None
            product.supplier_id = request.POST.get('supplier_id') or None
            product.main_image_url = request.POST.get('main_image_url', '').strip() or None
            product.image_url_1 = request.POST.get('image_url_1', '').strip() or None
            product.image_url_2 = request.POST.get('image_url_2', '').strip() or None
            product.image_url_3 = request.POST.get('image_url_3', '').strip() or None
            product.image_url_4 = request.POST.get('image_url_4', '').strip() or None
            # Автоматически отключаем товар, если остаток 0
            is_available_param = request.POST.get('is_available') == 'on'
            if stock_qty <= 0:
                is_available_param = False
            product.is_available = is_available_param
            product.save()
            
            # Обновляем размеры
            existing_sizes = {s.id: s for s in product.sizes.all()}
            size_ids = request.POST.getlist('size_id')
            size_labels = request.POST.getlist('size_label')
            size_stocks = request.POST.getlist('size_stock')
            
            # Удаляем размеры, которых нет в форме
            submitted_ids = [int(sid) for sid in size_ids if sid]
            for size_id, size in existing_sizes.items():
                if size_id not in submitted_ids:
                    size.delete()
            
            # Обновляем или создаем размеры
            for size_id, label, stock in zip(size_ids, size_labels, size_stocks):
                if label.strip():
                    if size_id:
                        try:
                            size = ProductSize.objects.get(pk=size_id, product=product)
                            size.size_label = label.strip()
                            size.size_stock = int(stock or '0')
                            size.save()
                        except ProductSize.DoesNotExist:
                            pass
                    else:
                        ProductSize.objects.create(
                            product=product,
                            size_label=label.strip(),
                            size_stock=int(stock or '0')
                        )
            
            # Обновляем теги
            ProductTag.objects.filter(product=product).delete()
            tag_ids = request.POST.getlist('tags')
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass
            
            _log_activity(request.user, 'update', f'product_{product_id}', f'Обновлен товар: {product.product_name}', request)
            messages.success(request, 'Товар успешно обновлен')
            return redirect('manager_products_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении товара: {str(e)}')
    
    return render(request, 'main/manager/product_edit.html', {
        'product': product,
        'categories': categories,
        'brands': brands,
        'suppliers': suppliers,
        'tags': tags,
        'product_tags': product_tags
    })

@login_required
def manager_product_delete(request, product_id):
    """Удаление товара"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    product = get_object_or_404(Product, pk=product_id)
    
    if request.method == 'POST':
        product_name = product.product_name
        product_id_val = product.id
        product.delete()
        _log_activity(request.user, 'delete', f'product_{product_id_val}', f'Удален товар: {product_name}', request)
        messages.success(request, f'Товар "{product_name}" удален')
        return redirect('manager_products_list')
    
    return render(request, 'main/manager/product_delete.html', {'product': product})

# =================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ И БРЕНДАМИ ===================

@login_required
def manager_categories_list(request):
    """Список категорий"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    categories = Category.objects.all().order_by('category_name')
    brands = Brand.objects.all().order_by('brand_name')
    
    return render(request, 'main/manager/categories_list.html', {
        'categories': categories,
        'brands': brands
    })

@login_required
def manager_category_add(request):
    """Добавление категории"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        category = Category.objects.create(
            category_name=request.POST.get('category_name', '').strip(),
            category_description=request.POST.get('category_description', '').strip(),
            parent_category_id=request.POST.get('parent_category_id') or None
        )
        _log_activity(request.user, 'create', f'category_{category.id}', f'Создана категория: {category.category_name}', request)
        messages.success(request, 'Категория добавлена')
        return redirect('manager_categories_list')
    
    categories = Category.objects.all()
    return render(request, 'main/manager/category_edit.html', {
        'category': None,
        'categories': categories
    })

@login_required
def manager_category_edit(request, category_id):
    """Редактирование категории"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    category = get_object_or_404(Category, pk=category_id)
    
    if request.method == 'POST':
        old_name = category.category_name
        category.category_name = request.POST.get('category_name', '').strip()
        category.category_description = request.POST.get('category_description', '').strip()
        category.parent_category_id = request.POST.get('parent_category_id') or None
        category.save()
        _log_activity(request.user, 'update', f'category_{category_id}', f'Обновлена категория: {old_name} -> {category.category_name}', request)
        messages.success(request, 'Категория обновлена')
        return redirect('manager_categories_list')
    
    categories = Category.objects.exclude(pk=category_id)
    return render(request, 'main/manager/category_edit.html', {
        'category': category,
        'categories': categories
    })

@login_required
def manager_brand_add(request):
    """Добавление бренда"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        brand = Brand.objects.create(
            brand_name=request.POST.get('brand_name', '').strip(),
            brand_country=request.POST.get('brand_country', '').strip() or None,
            brand_description=request.POST.get('brand_description', '').strip() or None
        )
        _log_activity(request.user, 'create', f'brand_{brand.id}', f'Создан бренд: {brand.brand_name}', request)
        messages.success(request, 'Бренд добавлен')
        return redirect('manager_categories_list')
    
    return render(request, 'main/manager/brand_edit.html', {'brand': None})

@login_required
def manager_brand_edit(request, brand_id):
    """Редактирование бренда"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    brand = get_object_or_404(Brand, pk=brand_id)
    
    if request.method == 'POST':
        old_name = brand.brand_name
        brand.brand_name = request.POST.get('brand_name', '').strip()
        brand.brand_country = request.POST.get('brand_country', '').strip() or None
        brand.brand_description = request.POST.get('brand_description', '').strip() or None
        brand.save()
        _log_activity(request.user, 'update', f'brand_{brand_id}', f'Обновлен бренд: {old_name} -> {brand.brand_name}', request)
        messages.success(request, 'Бренд обновлен')
        return redirect('manager_categories_list')
    
    return render(request, 'main/manager/brand_edit.html', {'brand': brand})

# =================== УПРАВЛЕНИЕ ЗАКАЗАМИ ===================

@login_required
def manager_orders_list(request):
    """Список заказов для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status')
    
    qs = Order.objects.select_related('user', 'address').prefetch_related('items').all().order_by('-created_at')
    
    if q:
        qs = qs.filter(Q(id__icontains=q) | Q(user__username__icontains=q) | Q(user__email__icontains=q))
    if status_filter:
        qs = qs.filter(order_status=status_filter)
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    
    return render(request, 'main/manager/orders_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'statuses': Order.ORDER_STATUSES
    })

@login_required
def manager_order_detail(request, order_id):
    """Детали заказа для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    order = get_object_or_404(Order, pk=order_id)
    items = order.items.select_related('product', 'size').all()
    delivery = getattr(order, 'delivery', None)
    
    # Вычисляем общую сумму для каждого товара
    items_with_total = []
    for item in items:
        item_total = float(item.unit_price) * item.quantity
        items_with_total.append({
            'item': item,
            'total': item_total
        })
    
    if request.method == 'POST':
        old_status = order.order_status
        new_status = request.POST.get('order_status')
        if new_status in dict(Order.ORDER_STATUSES):
            order.order_status = new_status
            order.save()
            
            # Если статус "отправлен", создаем или обновляем доставку
            if new_status == 'shipped':
                delivery, created = Delivery.objects.get_or_create(order=order)
                delivery.carrier_name = request.POST.get('carrier_name', '').strip() or None
                delivery.tracking_number = request.POST.get('tracking_number', '').strip() or None
                delivery.delivery_status = 'in_transit'
                if not delivery.shipped_at:
                    delivery.shipped_at = timezone.now()
                delivery.save()
            
            if old_status != new_status:
                _log_activity(request.user, 'update', f'order_{order_id}', f'Изменен статус заказа: {old_status} -> {new_status}', request)
            messages.success(request, 'Статус заказа обновлен')
            return redirect('manager_order_detail', order_id=order.id)
    
    return render(request, 'main/manager/order_detail.html', {
        'order': order,
        'items': items_with_total,
        'delivery': delivery,
        'statuses': Order.ORDER_STATUSES
    })

# =================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===================

@login_required
def manager_users_list(request):
    """Список пользователей для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status')
    role_filter = request.GET.get('role')
    activity_filter = request.GET.get('activity')  # active, inactive
    
    qs = User.objects.select_related('profile').all().order_by('-date_joined')
    
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if status_filter:
        qs = qs.filter(profile__user_status=status_filter)
    if role_filter:
        qs = qs.filter(profile__role_id=role_filter)
    if activity_filter == 'active':
        # Пользователи с заказами за последние 30 дней
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        qs = qs.filter(order__created_at__gte=month_ago).distinct()
    elif activity_filter == 'inactive':
        # Пользователи без заказов за последние 30 дней
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        qs = qs.exclude(order__created_at__gte=month_ago).distinct()
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    roles = Role.objects.all().order_by('role_name')
    
    return render(request, 'main/manager/users_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'role_filter': role_filter,
        'activity_filter': activity_filter,
        'roles': roles
    })

@login_required
def manager_user_toggle_block(request, user_id):
    """Блокировка/разблокировка пользователя"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    from django.contrib.auth.models import User as AuthUser
    user = get_object_or_404(AuthUser, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    old_status = profile.user_status
    profile.user_status = 'active' if profile.user_status == 'blocked' else 'blocked'
    profile.save()
    # Также устанавливаем is_active для дополнительной защиты
    user.is_active = (profile.user_status == 'active')
    user.save()
    _log_activity(request.user, 'update', f'user_{user_id}', f'Изменен статус пользователя: {old_status} -> {profile.user_status}', request)
    messages.success(request, f'Пользователь {"разблокирован" if profile.user_status == "active" else "заблокирован"}')
    return redirect('manager_users_list')

# =================== УПРАВЛЕНИЕ ПОДДЕРЖКОЙ ===================

@login_required
def manager_support_list(request):
    """Список обращений в поддержку для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status')
    
    qs = SupportTicket.objects.select_related('user').all().order_by('-created_at')
    
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(message_text__icontains=q) | Q(user__username__icontains=q))
    if status_filter:
        qs = qs.filter(ticket_status=status_filter)
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    
    return render(request, 'main/manager/support_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter
    })

@login_required
def manager_support_detail(request, ticket_id):
    """Детали обращения в поддержку для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    
    if request.method == 'POST':
        ticket.response_text = request.POST.get('response_text', '').strip()
        ticket.ticket_status = request.POST.get('ticket_status', 'new')
        ticket.save()
        _log_activity(request.user, 'update', f'ticket_{ticket_id}', f'Обновлено обращение в поддержку: {ticket.subject}', request)
        messages.success(request, 'Ответ сохранен')
        return redirect('manager_support_detail', ticket_id=ticket.id)
    
    return render(request, 'main/manager/support_detail.html', {'ticket': ticket})

# =================== АНАЛИТИКА И ОТЧЁТЫ ===================

@login_required
def manager_analytics(request):
    """Аналитика для менеджера"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    from django.db.models import Count, Sum, Avg, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Периоды
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Статистика по заказам
    orders_today = Order.objects.filter(created_at__date=today).count()
    orders_week = Order.objects.filter(created_at__date__gte=week_ago).count()
    orders_month = Order.objects.filter(created_at__date__gte=month_ago).count()
    
    revenue_today = Order.objects.filter(created_at__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    revenue_week = Order.objects.filter(created_at__date__gte=week_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    revenue_month = Order.objects.filter(created_at__date__gte=month_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    
    # Товар недели (по количеству продаж)
    product_of_week = Product.objects.filter(
        orderitem__order__created_at__date__gte=week_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold').first()
    
    # Товар месяца
    product_of_month = Product.objects.filter(
        orderitem__order__created_at__date__gte=month_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold').first()
    
    # Популярные товары
    popular_products = Product.objects.filter(
        orderitem__order__created_at__date__gte=month_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold')[:10]
    
    # Статистика по категориям
    category_stats = Category.objects.annotate(
        total_products=Count('product'),
        total_sold=Sum('product__orderitem__quantity'),
        total_revenue=Sum(F('product__orderitem__quantity') * F('product__orderitem__unit_price'))
    ).order_by('-total_revenue')[:10]
    
    stats = {
        'orders_today': orders_today,
        'orders_week': orders_week,
        'orders_month': orders_month,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,
        'product_of_week': product_of_week,
        'product_of_month': product_of_month,
        'popular_products': popular_products,
        'category_stats': category_stats,
    }
    
    return render(request, 'main/manager/analytics.html', stats)

@login_required
def manager_analytics_export_csv(request):
    """Экспорт отчёта в CSV"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    import csv
    from django.http import HttpResponse
    from django.db.models import Sum, F
    
    report_type = request.GET.get('type', 'sales')  # sales, products, users
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response.write('\ufeff')  # BOM для корректного отображения кириллицы в Excel
    
    if report_type == 'sales':
        response['Content-Disposition'] = 'attachment; filename="отчет_по_продажам.csv"'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID заказа', 'Пользователь', 'Email', 'Сумма (₽)', 'Статус', 'Дата создания'])
        for order in Order.objects.select_related('user').all().order_by('-created_at')[:1000]:
            writer.writerow([
                order.id,
                order.user.username if order.user else '',
                order.user.email if order.user else '',
                order.total_amount,
                order.get_order_status_display(),
                order.created_at.strftime('%Y-%m-%d %H:%M')
            ])
    elif report_type == 'products':
        response['Content-Disposition'] = 'attachment; filename="отчет_по_товарам.csv"'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID', 'Название', 'Категория', 'Бренд', 'Цена (₽)', 'Скидка (%)', 'Остаток (шт.)', 'Продано (шт.)', 'Доступен'])
        for product in Product.objects.select_related('category', 'brand').annotate(
            total_sold=Sum('orderitem__quantity')
        ).all():
            writer.writerow([
                product.id,
                product.product_name,
                product.category.category_name if product.category else '',
                product.brand.brand_name if product.brand else '',
                product.price,
                product.discount,
                product.stock_quantity,
                product.total_sold or 0,
                'Да' if product.is_available else 'Нет'
            ])
    elif report_type == 'users':
        response['Content-Disposition'] = 'attachment; filename="отчет_по_пользователям.csv"'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID', 'Логин', 'Email', 'Имя', 'Фамилия', 'Роль', 'Статус', 'Баланс (₽)', 'Заказов', 'Дата регистрации'])
        for user in User.objects.select_related('profile').annotate(
            total_orders=Count('order')
        ).all():
            profile = getattr(user, 'profile', None)
            writer.writerow([
                user.id,
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                profile.role.role_name if profile and profile.role else '',
                profile.user_status if profile else '',
                profile.balance if profile else 0,
                user.total_orders,
                user.date_joined.strftime('%Y-%m-%d %H:%M')
            ])
    
    return response

@login_required
def manager_analytics_export_pdf(request):
    """Экспорт отчёта в PDF"""
    if not _user_is_manager(request.user):
        return redirect('profile')
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from io import BytesIO
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        y = height - 20 * mm
        line_height = 6 * mm
        left_margin = 15 * mm
        
        # Используем шрифт с поддержкой кириллицы
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import platform
        import os
        
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"
        
        # Пытаемся использовать системные шрифты с поддержкой кириллицы
        try:
            system = platform.system()
            arial_found = False
            
            # Для Windows используем системные шрифты
            if system == 'Windows':
                font_dir = r'C:\Windows\Fonts'
                
                # Список возможных путей к Arial
                arial_variants = [
                    'arial.ttf',
                    'Arial.ttf',
                    'ARIAL.TTF',
                    'arialuni.ttf',  # Arial Unicode MS (полная поддержка Unicode)
                ]
                
                arial_bold_variants = [
                    'arialbd.ttf',
                    'Arialbd.ttf',
                    'ARIALBD.TTF',
                ]
                
                # Пробуем найти и зарегистрировать Arial
                for variant in arial_variants:
                    arial_path = os.path.join(font_dir, variant)
                    if os.path.exists(arial_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Arial', arial_path))
                            font_name = 'Arial'
                            arial_found = True
                            break
                        except Exception:
                            continue
                
                # Пробуем найти и зарегистрировать Arial Bold
                if arial_found:
                    for variant in arial_bold_variants:
                        arial_bold_path = os.path.join(font_dir, variant)
                        if os.path.exists(arial_bold_path):
                            try:
                                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                                font_bold = 'Arial-Bold'
                                break
                            except Exception:
                                pass
            # Для Linux используем DejaVu Sans
            elif system == 'Linux':
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
                    font_name = 'DejaVuSans'
                    font_bold = 'DejaVuSans-Bold'
                except Exception:
                    pass
        except Exception:
            pass
        
        def draw(text, bold=False, font_size=10):
            nonlocal y
            current_font = font_bold if bold else font_name
            c.setFont(current_font, font_size)
            c.drawString(left_margin, y, str(text))
            y -= line_height
        
        draw("Отчёт по продажам", bold=True, font_size=16)
        draw(f"Дата: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
        y -= 5 * mm
        
        # Статистика
        month_ago = timezone.now() - timedelta(days=30)
        orders_count = Order.objects.filter(created_at__gte=month_ago).count()
        revenue = Order.objects.filter(created_at__gte=month_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        draw("Статистика за последний месяц:", bold=True)
        draw(f"Заказов: {orders_count}")
        draw(f"Выручка: {revenue} ₽")
        y -= 5 * mm
        
        # Популярные товары
        draw("Популярные товары:", bold=True)
        popular = Product.objects.filter(
            orderitem__order__created_at__gte=month_ago
        ).annotate(
            total_sold=Sum('orderitem__quantity')
        ).order_by('-total_sold')[:10]
        
        for i, product in enumerate(popular, 1):
            draw(f"{i}. {product.product_name} - продано: {product.total_sold or 0} шт.")
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="отчет_по_продажам.pdf"'
        return response
        
    except ImportError:
        messages.error(request, "PDF генератор не установлен. Пожалуйста, установите reportlab.")
        return redirect('manager_analytics')

# =================== ПАНЕЛЬ АДМИНИСТРАТОРА ===================

# =================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ И РОЛЯМИ ===================

@login_required
def admin_users_list(request):
    """Расширенный список пользователей для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'users_list', 'Просмотр списка пользователей', request)
    
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status')
    role_filter = request.GET.get('role')
    activity_filter = request.GET.get('activity')
    
    qs = User.objects.select_related('profile').all().order_by('-date_joined')
    
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if status_filter:
        qs = qs.filter(profile__user_status=status_filter)
    if role_filter:
        qs = qs.filter(profile__role_id=role_filter)
    if activity_filter == 'active':
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        qs = qs.filter(order__created_at__gte=month_ago).distinct()
    elif activity_filter == 'inactive':
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        qs = qs.exclude(order__created_at__gte=month_ago).distinct()
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    roles = Role.objects.all().order_by('role_name')
    
    return render(request, 'main/admin/users_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'role_filter': role_filter,
        'activity_filter': activity_filter,
        'roles': roles
    })

@login_required
def admin_user_create(request):
    """Создание нового пользователя"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    roles = Role.objects.all().order_by('role_name')
    
    if request.method == 'POST':
        try:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            role_id = request.POST.get('role_id')
            user_status = request.POST.get('user_status', 'active')
            
            if not username or not email or not password:
                messages.error(request, 'Логин, email и пароль обязательны')
                return render(request, 'main/admin/user_edit.html', {
                    'user_obj': None,
                    'roles': roles,
                    'is_create': True
                })
            
            # Создаем пользователя
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Создаем профиль
            secret_word = request.POST.get('secret_word', '').strip()
            profile = UserProfile.objects.create(
                user=user,
                role_id=role_id if role_id else None,
                user_status=user_status,
                full_name=f"{first_name} {last_name}".strip(),
                secret_word=secret_word if secret_word else None
            )
            
            _log_activity(request.user, 'create', f'user_{user.id}', f'Создан пользователь: {username}', request)
            messages.success(request, f'Пользователь {username} успешно создан')
            return redirect('admin_user_edit', user_id=user.id)
        except Exception as e:
            messages.error(request, f'Ошибка при создании пользователя: {str(e)}')
    
    return render(request, 'main/admin/user_edit.html', {
        'user_obj': None,
        'roles': roles,
        'is_create': True
    })

@login_required
def admin_user_edit(request, user_id):
    """Редактирование пользователя админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    user = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    roles = Role.objects.all().order_by('role_name')
    
    if request.method == 'POST':
        try:
            user.username = request.POST.get('username', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            
            new_password = request.POST.get('password', '').strip()
            if new_password:
                user.set_password(new_password)
                _log_activity(request.user, 'update', f'user_{user.id}', 'Изменен пароль пользователя', request)
            
            user.is_active = request.POST.get('is_active') == 'on'
            user.is_staff = request.POST.get('is_staff') == 'on'
            user.is_superuser = request.POST.get('is_superuser') == 'on'
            user.save()
            
            # Обновляем профиль
            profile.full_name = request.POST.get('full_name', '').strip()
            profile.phone_number = request.POST.get('phone_number', '').strip()
            birth_date_str = request.POST.get('birth_date', '').strip()
            if birth_date_str:
                try:
                    from datetime import datetime
                    profile.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            balance_str = request.POST.get('balance', '').strip()
            if balance_str:
                try:
                    profile.balance = Decimal(balance_str)
                except (ValueError, InvalidOperation):
                    pass
            
            # Обновление секретного слова (только если указано)
            secret_word = request.POST.get('secret_word', '').strip()
            if secret_word:
                profile.secret_word = secret_word
                _log_activity(request.user, 'update', f'user_{user.id}', 'Изменено секретное слово пользователя', request)
            
            role_id = request.POST.get('role_id')
            if role_id:
                try:
                    old_role = profile.role.role_name if profile.role else None
                    profile.role = Role.objects.get(pk=role_id)
                    new_role = profile.role.role_name
                    if old_role != new_role:
                        _log_activity(request.user, 'update', f'user_{user.id}', f'Изменена роль: {old_role} -> {new_role}', request)
                except Role.DoesNotExist:
                    profile.role = None
            else:
                profile.role = None
            
            old_status = profile.user_status
            profile.user_status = 'blocked' if request.POST.get('blocked') == 'on' else 'active'
            if old_status != profile.user_status:
                _log_activity(request.user, 'update', f'user_{user.id}', f'Изменен статус: {old_status} -> {profile.user_status}', request)
            
            profile.save()
            # Также устанавливаем is_active для дополнительной защиты
            user.is_active = (profile.user_status == 'active')
            user.save()
            
            _log_activity(request.user, 'update', f'user_{user.id}', f'Обновлен пользователь: {user.username}', request)
            messages.success(request, 'Пользователь обновлен')
            return redirect('admin_users_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    return render(request, 'main/admin/user_edit.html', {
        'user_obj': user,
        'profile': profile,
        'roles': roles,
        'is_create': False
    })

@login_required
def admin_user_delete(request, user_id):
    """Удаление пользователя"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    user = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        username = user.username
        user_id_val = user.id
        user.delete()
        _log_activity(request.user, 'delete', f'user_{user_id_val}', f'Удален пользователь: {username}', request)
        messages.success(request, f'Пользователь {username} удален')
        return redirect('admin_users_list')
    
    return render(request, 'main/admin/user_delete.html', {'user_obj': user})

@login_required
def admin_roles_list(request):
    """Управление ролями"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'roles_list', 'Просмотр списка ролей', request)
    
    roles = Role.objects.all().order_by('role_name')
    
    if request.method == 'POST' and request.POST.get('action') == 'create':
        role_name = request.POST.get('role_name', '').strip()
        if role_name:
            role, created = Role.objects.get_or_create(role_name=role_name)
            if created:
                _log_activity(request.user, 'create', f'role_{role.id}', f'Создана роль: {role_name}', request)
                messages.success(request, 'Роль создана')
            else:
                messages.info(request, 'Роль уже существует')
        return redirect('admin_roles_list')
    
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        role_id = request.POST.get('role_id')
        try:
            role = Role.objects.get(pk=role_id)
            role_name = role.role_name
            role.delete()
            _log_activity(request.user, 'delete', f'role_{role_id}', f'Удалена роль: {role_name}', request)
            messages.success(request, 'Роль удалена')
        except Role.DoesNotExist:
            messages.error(request, 'Роль не найдена')
        return redirect('admin_roles_list')
    
    return render(request, 'main/admin/roles_list.html', {'roles': roles})

# =================== УПРАВЛЕНИЕ ТОВАРАМИ, КАТЕГОРИЯМИ И БРЕНДАМИ ===================

@login_required
def admin_products_list(request):
    """Список товаров для админа (с логированием)"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'products_list', 'Просмотр списка товаров', request)
    
    # Используем ту же логику, что и у менеджера, но с логированием
    return manager_products_list(request)

@login_required
def admin_product_add(request):
    """Добавление товара админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    suppliers = Supplier.objects.all()
    tags = Tag.objects.all()
    
    if request.method == 'POST':
        try:
            stock_qty = int(request.POST.get('stock_quantity', '0'))
            is_available_param = request.POST.get('is_available') == 'on'
            # Автоматически отключаем товар, если остаток 0
            if stock_qty <= 0:
                is_available_param = False
            
            product = Product.objects.create(
                product_name=request.POST.get('product_name', '').strip(),
                product_description=request.POST.get('product_description', '').strip(),
                price=Decimal(request.POST.get('price', '0')),
                discount=Decimal(request.POST.get('discount', '0')),
                stock_quantity=stock_qty,
                category_id=request.POST.get('category_id') or None,
                brand_id=request.POST.get('brand_id') or None,
                supplier_id=request.POST.get('supplier_id') or None,
                main_image_url=request.POST.get('main_image_url', '').strip() or None,
                image_url_1=request.POST.get('image_url_1', '').strip() or None,
                image_url_2=request.POST.get('image_url_2', '').strip() or None,
                image_url_3=request.POST.get('image_url_3', '').strip() or None,
                image_url_4=request.POST.get('image_url_4', '').strip() or None,
                is_available=is_available_param
            )
            
            # Добавляем размеры
            size_labels = request.POST.getlist('size_label')
            size_stocks = request.POST.getlist('size_stock')
            for label, stock in zip(size_labels, size_stocks):
                if label.strip():
                    ProductSize.objects.create(
                        product=product,
                        size_label=label.strip(),
                        size_stock=int(stock or '0')
                    )
            
            # Добавляем теги
            tag_ids = request.POST.getlist('tags')
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.get_or_create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass
            
            _log_activity(request.user, 'create', f'product_{product.id}', f'Создан товар: {product.product_name}', request)
            messages.success(request, 'Товар успешно добавлен')
            return redirect('admin_products_list')
        except Exception as e:
            messages.error(request, f'Ошибка при добавлении товара: {str(e)}')
    
    return render(request, 'main/manager/product_edit.html', {
        'product': None,
        'categories': categories,
        'brands': brands,
        'suppliers': suppliers,
        'tags': tags
    })

@login_required
def admin_product_edit(request, product_id):
    """Редактирование товара админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    product = get_object_or_404(Product, pk=product_id)
    categories = Category.objects.all()
    brands = Brand.objects.all()
    suppliers = Supplier.objects.all()
    tags = Tag.objects.all()
    product_tags = [pt.tag.id for pt in product.producttag_set.all()]
    old_name = product.product_name
    
    if request.method == 'POST':
        try:
            product.product_name = request.POST.get('product_name', '').strip()
            product.product_description = request.POST.get('product_description', '').strip()
            product.price = Decimal(request.POST.get('price', '0'))
            product.discount = Decimal(request.POST.get('discount', '0'))
            stock_qty = int(request.POST.get('stock_quantity', '0'))
            product.stock_quantity = stock_qty
            product.category_id = request.POST.get('category_id') or None
            product.brand_id = request.POST.get('brand_id') or None
            product.supplier_id = request.POST.get('supplier_id') or None
            product.main_image_url = request.POST.get('main_image_url', '').strip() or None
            product.image_url_1 = request.POST.get('image_url_1', '').strip() or None
            product.image_url_2 = request.POST.get('image_url_2', '').strip() or None
            product.image_url_3 = request.POST.get('image_url_3', '').strip() or None
            product.image_url_4 = request.POST.get('image_url_4', '').strip() or None
            # Автоматически отключаем товар, если остаток 0
            is_available_param = request.POST.get('is_available') == 'on'
            if stock_qty <= 0:
                is_available_param = False
            product.is_available = is_available_param
            product.save()
            
            # Обновляем размеры
            existing_sizes = {s.id: s for s in product.sizes.all()}
            size_ids = request.POST.getlist('size_id')
            size_labels = request.POST.getlist('size_label')
            size_stocks = request.POST.getlist('size_stock')
            
            # Удаляем размеры, которых нет в форме
            submitted_ids = [int(sid) for sid in size_ids if sid]
            for size_id, size in existing_sizes.items():
                if size_id not in submitted_ids:
                    size.delete()
            
            # Обновляем или создаем размеры
            for size_id, label, stock in zip(size_ids, size_labels, size_stocks):
                if label.strip():
                    if size_id:
                        try:
                            size = ProductSize.objects.get(pk=size_id, product=product)
                            size.size_label = label.strip()
                            size.size_stock = int(stock or '0')
                            size.save()
                        except ProductSize.DoesNotExist:
                            pass
                    else:
                        ProductSize.objects.create(
                            product=product,
                            size_label=label.strip(),
                            size_stock=int(stock or '0')
                        )
            
            # Обновляем теги
            ProductTag.objects.filter(product=product).delete()
            tag_ids = request.POST.getlist('tags')
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass
            
            _log_activity(request.user, 'update', f'product_{product_id}', f'Обновлен товар: {old_name} -> {product.product_name}', request)
            messages.success(request, 'Товар успешно обновлен')
            return redirect('admin_products_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении товара: {str(e)}')
    
    return render(request, 'main/manager/product_edit.html', {
        'product': product,
        'categories': categories,
        'brands': brands,
        'suppliers': suppliers,
        'tags': tags,
        'product_tags': product_tags
    })

@login_required
def admin_product_delete(request, product_id):
    """Удаление товара админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    product = get_object_or_404(Product, pk=product_id)
    product_name = product.product_name
    
    if request.method == 'POST':
        product.delete()
        _log_activity(request.user, 'delete', f'product_{product_id}', f'Удален товар: {product_name}', request)
        messages.success(request, f'Товар "{product_name}" удален')
        return redirect('admin_products_list')
    
    return render(request, 'main/manager/product_delete.html', {'product': product})

# =================== УПРАВЛЕНИЕ ЗАКАЗАМИ И ДОСТАВКОЙ ===================

@login_required
def admin_orders_list(request):
    """Список заказов для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'orders_list', 'Просмотр списка заказов', request)
    
    # Используем ту же логику, что и у менеджера
    return manager_orders_list(request)

@login_required
def admin_order_detail(request, order_id):
    """Детали заказа для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    order = get_object_or_404(Order, pk=order_id)
    
    if request.method == 'POST':
        old_status = order.order_status
        new_status = request.POST.get('order_status')
        if new_status in dict(Order.ORDER_STATUSES):
            order.order_status = new_status
            order.save()
            
            if old_status != new_status:
                _log_activity(request.user, 'update', f'order_{order_id}', f'Изменен статус заказа: {old_status} -> {new_status}', request)
            
            # Если статус "отправлен", создаем или обновляем доставку
            if new_status == 'shipped':
                delivery, created = Delivery.objects.get_or_create(order=order)
                delivery.carrier_name = request.POST.get('carrier_name', '').strip() or None
                delivery.tracking_number = request.POST.get('tracking_number', '').strip() or None
                delivery.delivery_status = 'in_transit'
                if not delivery.shipped_at:
                    delivery.shipped_at = timezone.now()
                delivery.save()
                _log_activity(request.user, 'update', f'order_{order_id}', f'Назначен курьер: {delivery.carrier_name}', request)
            
            messages.success(request, 'Статус заказа обновлен')
            return redirect('admin_order_detail', order_id=order.id)
    
    items = order.items.select_related('product', 'size').all()
    items_with_total = []
    for item in items:
        item_total = float(item.unit_price) * item.quantity
        items_with_total.append({
            'item': item,
            'total': item_total
        })
    delivery = getattr(order, 'delivery', None)
    
    return render(request, 'main/admin/order_detail.html', {
        'order': order,
        'items': items_with_total,
        'delivery': delivery,
        'statuses': Order.ORDER_STATUSES
    })

# =================== УПРАВЛЕНИЕ ПОДДЕРЖКОЙ ===================

@login_required
def admin_support_list(request):
    """Список обращений для админа с назначением ответственных"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'support_list', 'Просмотр списка обращений', request)
    
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status')
    assigned_filter = request.GET.get('assigned')
    
    qs = SupportTicket.objects.select_related('user', 'assigned_to').all().order_by('-created_at')
    
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(message_text__icontains=q) | Q(user__username__icontains=q))
    if status_filter:
        qs = qs.filter(ticket_status=status_filter)
    if assigned_filter == 'assigned':
        qs = qs.exclude(assigned_to__isnull=True)
    elif assigned_filter == 'unassigned':
        qs = qs.filter(assigned_to__isnull=True)
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    
    # Список менеджеров для назначения
    managers = User.objects.filter(
        Q(is_superuser=True) | 
        Q(profile__role__role_name__iexact='manager') |
        Q(profile__role__role_name__iexact='менеджер') |
        Q(profile__role__role_name__iexact='admin') |
        Q(profile__role__role_name__iexact='админ')
    ).distinct()
    
    return render(request, 'main/admin/support_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'assigned_filter': assigned_filter,
        'managers': managers
    })

@login_required
def admin_support_detail(request, ticket_id):
    """Детали обращения для админа с назначением ответственного"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    
    if request.method == 'POST':
        old_assigned = ticket.assigned_to.username if ticket.assigned_to else None
        assigned_to_id = request.POST.get('assigned_to')
        
        if assigned_to_id:
            try:
                assigned_user = User.objects.get(pk=assigned_to_id)
                ticket.assigned_to = assigned_user
                new_assigned = assigned_user.username
                if old_assigned != new_assigned:
                    _log_activity(request.user, 'update', f'ticket_{ticket_id}', f'Назначен ответственный: {new_assigned}', request)
            except User.DoesNotExist:
                pass
        else:
            ticket.assigned_to = None
            if old_assigned:
                _log_activity(request.user, 'update', f'ticket_{ticket_id}', 'Снят ответственный', request)
        
        ticket.response_text = request.POST.get('response_text', '').strip()
        old_status = ticket.ticket_status
        ticket.ticket_status = request.POST.get('ticket_status', 'new')
        if old_status != ticket.ticket_status:
            _log_activity(request.user, 'update', f'ticket_{ticket_id}', f'Изменен статус: {old_status} -> {ticket.ticket_status}', request)
        
        ticket.save()
        _log_activity(request.user, 'update', f'ticket_{ticket_id}', 'Обновлено обращение в поддержку', request)
        messages.success(request, 'Обращение обновлено')
        return redirect('admin_support_detail', ticket_id=ticket.id)
    
    managers = User.objects.filter(
        Q(is_superuser=True) | 
        Q(profile__role__role_name__iexact='manager') |
        Q(profile__role__role_name__iexact='менеджер') |
        Q(profile__role__role_name__iexact='admin') |
        Q(profile__role__role_name__iexact='админ')
    ).distinct()
    
    return render(request, 'main/admin/support_detail.html', {
        'ticket': ticket,
        'managers': managers
    })

# =================== АНАЛИТИКА И ОТЧЁТЫ ===================

@login_required
def admin_analytics(request):
    """Расширенная аналитика для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'analytics', 'Просмотр аналитики', request)
    
    from django.db.models import Count, Sum, Avg, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Периоды
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)
    
    # Статистика по заказам
    orders_today = Order.objects.filter(created_at__date=today).count()
    orders_week = Order.objects.filter(created_at__date__gte=week_ago).count()
    orders_month = Order.objects.filter(created_at__date__gte=month_ago).count()
    orders_year = Order.objects.filter(created_at__date__gte=year_ago).count()
    
    revenue_today = Order.objects.filter(created_at__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    revenue_week = Order.objects.filter(created_at__date__gte=week_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    revenue_month = Order.objects.filter(created_at__date__gte=month_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    revenue_year = Order.objects.filter(created_at__date__gte=year_ago).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
    
    # Статистика по пользователям
    total_users = User.objects.count()
    active_users = UserProfile.objects.filter(user_status='active').count()
    blocked_users = UserProfile.objects.filter(user_status='blocked').count()
    new_users_month = User.objects.filter(date_joined__gte=month_ago).count()
    
    # Статистика по товарам
    total_products = Product.objects.count()
    available_products = Product.objects.filter(is_available=True).count()
    out_of_stock = Product.objects.filter(stock_quantity=0).count()
    
    # Товар недели/месяца
    product_of_week = Product.objects.filter(
        orderitem__order__created_at__date__gte=week_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold').first()
    
    product_of_month = Product.objects.filter(
        orderitem__order__created_at__date__gte=month_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold').first()
    
    # Популярные товары
    popular_products = Product.objects.filter(
        orderitem__order__created_at__date__gte=month_ago
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price'))
    ).order_by('-total_sold')[:10]
    
    # Статистика по категориям
    category_stats = Category.objects.annotate(
        total_products=Count('product'),
        total_sold=Sum('product__orderitem__quantity'),
        total_revenue=Sum(F('product__orderitem__quantity') * F('product__orderitem__unit_price'))
    ).order_by('-total_revenue')[:10]
    
    # Активность пользователей
    active_users_list = User.objects.filter(
        order__created_at__gte=month_ago
    ).annotate(
        total_orders=Count('order'),
        total_spent=Sum('order__total_amount')
    ).order_by('-total_spent')[:10]
    
    # Статистика по налогам
    total_tax_month = Order.objects.filter(
        created_at__date__gte=month_ago,
        order_status__in=['paid', 'shipped', 'delivered']
    ).aggregate(Sum('tax_amount'))['tax_amount__sum'] or Decimal('0')
    
    total_tax_year = Order.objects.filter(
        created_at__date__gte=year_ago,
        order_status__in=['paid', 'shipped', 'delivered']
    ).aggregate(Sum('tax_amount'))['tax_amount__sum'] or Decimal('0')
    
    # Счет организации
    org_account = OrganizationAccount.get_account()
    
    stats = {
        'orders_today': orders_today,
        'orders_week': orders_week,
        'orders_month': orders_month,
        'orders_year': orders_year,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,
        'revenue_year': revenue_year,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'new_users_month': new_users_month,
        'total_products': total_products,
        'available_products': available_products,
        'out_of_stock': out_of_stock,
        'product_of_week': product_of_week,
        'product_of_month': product_of_month,
        'popular_products': popular_products,
        'category_stats': category_stats,
        'active_users_list': active_users_list,
        'total_tax_month': total_tax_month,
        'total_tax_year': total_tax_year,
        'org_balance': org_account.balance,
        'org_tax_reserve': org_account.tax_reserve,
    }
    
    return render(request, 'main/admin/analytics.html', stats)

@login_required
def admin_analytics_export_csv(request):
    """Расширенный экспорт отчётов в CSV"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'export', 'csv_report', 'Экспорт отчёта в CSV', request)
    
    return manager_analytics_export_csv(request)

@login_required
def admin_org_account(request):
    """Управление счетом организации"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    org_account = OrganizationAccount.get_account()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'withdraw':
            # Вывод средств на карту админа
            try:
                amount = Decimal(request.POST.get('amount', '0'))
            except (ValueError, InvalidOperation):
                messages.error(request, "Неверный формат суммы.")
                return redirect('admin_org_account')
            
            card_id = request.POST.get('card_id')
            
            if amount <= 0:
                messages.error(request, "Сумма должна быть больше нуля.")
                return redirect('admin_org_account')
            
            # Обновляем объект из БД для актуальных данных
            org_account.refresh_from_db()
            
            if not org_account.can_withdraw(amount):
                messages.error(request, f"Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽")
                return redirect('admin_org_account')
            
            if not card_id:
                messages.error(request, "Выберите карту для вывода средств.")
                return redirect('admin_org_account')
            
            try:
                card = SavedPaymentMethod.objects.get(id=card_id, user=request.user)
            except SavedPaymentMethod.DoesNotExist:
                messages.error(request, "Карта не найдена.")
                return redirect('admin_org_account')
            
            try:
                with transaction.atomic():
                    # Блокируем запись для обновления
                    org_account = OrganizationAccount.objects.select_for_update().get(pk=org_account.pk)
                    
                    # Повторная проверка после блокировки
                    if not org_account.can_withdraw(amount):
                        messages.error(request, f"Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽")
                        return redirect('admin_org_account')
                    
                    balance_before = org_account.balance
                    org_account.balance -= amount
                    org_account.save()
                    
                    card.balance += amount
                    card.save()
                    
                    # Создаем транзакции
                    OrganizationTransaction.objects.create(
                        organization_account=org_account,
                        transaction_type='withdrawal',
                        amount=amount,
                        description=f'Вывод на карту {card.mask_card_number()}',
                        created_by=request.user,
                        balance_before=balance_before,
                        balance_after=org_account.balance,
                        tax_reserve_before=org_account.tax_reserve,
                        tax_reserve_after=org_account.tax_reserve
                    )
                    
                    CardTransaction.objects.create(
                        saved_payment_method=card,
                        transaction_type='deposit',
                        amount=amount,
                        description=f'Поступление со счета организации',
                        status='completed'
                    )
                    
                    _log_activity(request.user, 'update', 'org_account', f'Вывод {amount} ₽ на карту {card.mask_card_number()}', request)
                    messages.success(request, f"Средства в размере {amount} ₽ переведены на карту {card.mask_card_number()}")
            except Exception as e:
                messages.error(request, f"Ошибка при выводе средств: {str(e)}")
                return redirect('admin_org_account')
        
        elif action == 'pay_tax':
            # Оплата налога
            try:
                amount = Decimal(request.POST.get('amount', '0'))
            except (ValueError, InvalidOperation):
                messages.error(request, "Неверный формат суммы.")
                return redirect('admin_org_account')
            
            if amount <= 0:
                messages.error(request, "Сумма должна быть больше нуля.")
                return redirect('admin_org_account')
            
            # Обновляем объект из БД для актуальных данных
            org_account.refresh_from_db()
            
            if not org_account.can_pay_tax(amount):
                if org_account.tax_reserve < amount:
                    messages.error(request, f"Недостаточно средств в резерве на налоги. Доступно: {org_account.tax_reserve} ₽, запрошено: {amount} ₽")
                elif org_account.balance < amount:
                    messages.error(request, f"Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽")
                else:
                    messages.error(request, f"Недостаточно средств для оплаты налога.")
                return redirect('admin_org_account')
            
            try:
                with transaction.atomic():
                    # Блокируем запись для обновления
                    org_account = OrganizationAccount.objects.select_for_update().get(pk=org_account.pk)
                    
                    # Повторная проверка после блокировки
                    if not org_account.can_pay_tax(amount):
                        if org_account.tax_reserve < amount:
                            messages.error(request, f"Недостаточно средств в резерве на налоги. Доступно: {org_account.tax_reserve} ₽, запрошено: {amount} ₽")
                        elif org_account.balance < amount:
                            messages.error(request, f"Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽")
                        else:
                            messages.error(request, f"Недостаточно средств для оплаты налога.")
                        return redirect('admin_org_account')
                    
                    balance_before = org_account.balance
                    tax_reserve_before = org_account.tax_reserve
                    
                    org_account.balance -= amount
                    org_account.tax_reserve -= amount
                    org_account.save()
                    
                    OrganizationTransaction.objects.create(
                        organization_account=org_account,
                        transaction_type='tax_payment',
                        amount=amount,
                        description=f'Оплата налога',
                        created_by=request.user,
                        balance_before=balance_before,
                        balance_after=org_account.balance,
                        tax_reserve_before=tax_reserve_before,
                        tax_reserve_after=org_account.tax_reserve
                    )
                    
                    _log_activity(request.user, 'update', 'org_account', f'Оплата налога {amount} ₽', request)
                    messages.success(request, f"Налог в размере {amount} ₽ оплачен")
            except Exception as e:
                messages.error(request, f"Ошибка при оплате налога: {str(e)}")
                return redirect('admin_org_account')
        
        return redirect('admin_org_account')
    
    # Получаем транзакции
    transactions = OrganizationTransaction.objects.filter(
        organization_account=org_account
    ).select_related('order', 'created_by').order_by('-created_at')[:50]
    
    # Получаем карты админа
    admin_cards = SavedPaymentMethod.objects.filter(user=request.user)
    
    return render(request, 'main/admin/org_account.html', {
        'org_account': org_account,
        'transactions': transactions,
        'admin_cards': admin_cards,
    })

@login_required
def admin_analytics_export_pdf(request):
    """Расширенный экспорт отчётов в PDF"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'export', 'pdf_report', 'Экспорт отчёта в PDF', request)
    
    return manager_analytics_export_pdf(request)

# =================== ЛОГИ АКТИВНОСТИ И АУДИТ ===================

@login_required
def admin_activity_logs(request):
    """Просмотр логов активности пользователей"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'activity_logs', 'Просмотр логов активности', request)
    
    q = (request.GET.get('q') or '').strip()
    action_filter = request.GET.get('action')
    user_filter = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    qs = ActivityLog.objects.select_related('user').all().order_by('-created_at')
    
    if q:
        qs = qs.filter(Q(action_description__icontains=q) | Q(target_object__icontains=q))
    if action_filter:
        qs = qs.filter(action_type=action_filter)
    if user_filter:
        qs = qs.filter(user_id=user_filter)
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            qs = qs.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            qs = qs.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    
    # Уникальные типы действий для фильтра
    action_types = ActivityLog.objects.values_list('action_type', flat=True).distinct()
    
    # Список пользователей для фильтра
    users_with_logs = User.objects.filter(activitylog__isnull=False).distinct()
    
    return render(request, 'main/admin/activity_logs.html', {
        'page_obj': page_obj,
        'q': q,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'action_types': action_types,
        'users_with_logs': users_with_logs
    })

@login_required
def admin_activity_log_detail(request, log_id):
    """Детали лога активности"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    log = get_object_or_404(ActivityLog, pk=log_id)
    
    return render(request, 'main/admin/activity_log_detail.html', {'log': log})

# =================== УПРАВЛЕНИЕ ПРОМОКОДАМИ ===================

@login_required
def admin_promotions_list(request):
    """Список промокодов для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'promotions_list', 'Просмотр списка промокодов', request)
    
    q = (request.GET.get('q') or '').strip()
    promotions = Promotion.objects.all().order_by('-id')
    
    if q:
        promotions = promotions.filter(
            Q(promo_code__icontains=q) | Q(promo_description__icontains=q)
        )
    
    paginator = Paginator(promotions, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'main/admin/promotions_list.html', {
        'page_obj': page_obj,
        'q': q
    })

@login_required
def admin_promotion_add(request):
    """Добавление промокода админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        try:
            promo_code = request.POST.get('promo_code', '').strip().upper()
            promo_description = request.POST.get('promo_description', '').strip()
            discount = Decimal(request.POST.get('discount', '0'))
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            if not promo_code:
                messages.error(request, 'Код промокода обязателен')
                return render(request, 'main/admin/promotion_edit.html', {'promotion': None})
            
            start_date = None
            end_date = None
            if start_date_str:
                try:
                    from datetime import datetime
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            if end_date_str:
                try:
                    from datetime import datetime
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            promotion = Promotion.objects.create(
                promo_code=promo_code,
                promo_description=promo_description,
                discount=discount,
                start_date=start_date,
                end_date=end_date,
                is_active=is_active
            )
            
            _log_activity(request.user, 'create', f'promotion_{promotion.id}', f'Создан промокод: {promo_code}', request)
            messages.success(request, f'Промокод {promo_code} создан')
            return redirect('admin_promotions_list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании промокода: {str(e)}')
    
    return render(request, 'main/admin/promotion_edit.html', {'promotion': None})

@login_required
def admin_promotion_edit(request, promo_id):
    """Редактирование промокода админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    promotion = get_object_or_404(Promotion, pk=promo_id)
    
    if request.method == 'POST':
        try:
            old_code = promotion.promo_code
            promotion.promo_code = request.POST.get('promo_code', '').strip().upper()
            promotion.promo_description = request.POST.get('promo_description', '').strip()
            promotion.discount = Decimal(request.POST.get('discount', '0'))
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            promotion.is_active = request.POST.get('is_active') == 'on'
            
            if start_date_str:
                try:
                    from datetime import datetime
                    promotion.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                promotion.start_date = None
                
            if end_date_str:
                try:
                    from datetime import datetime
                    promotion.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                promotion.end_date = None
            
            promotion.save()
            _log_activity(request.user, 'update', f'promotion_{promo_id}', f'Обновлен промокод: {old_code}', request)
            messages.success(request, 'Промокод обновлен')
            return redirect('admin_promotions_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    return render(request, 'main/admin/promotion_edit.html', {'promotion': promotion})

@login_required
def admin_promotion_delete(request, promo_id):
    """Удаление промокода админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    promotion = get_object_or_404(Promotion, pk=promo_id)
    
    if request.method == 'POST':
        promo_code = promotion.promo_code
        promotion.delete()
        _log_activity(request.user, 'delete', f'promotion_{promo_id}', f'Удален промокод: {promo_code}', request)
        messages.success(request, f'Промокод {promo_code} удален')
        return redirect('admin_promotions_list')
    
    return render(request, 'main/admin/promotion_delete.html', {'promotion': promotion})

# =================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ И БРЕНДАМИ ===================

@login_required
def admin_categories_list(request):
    """Список категорий и брендов для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'categories_list', 'Просмотр категорий и брендов', request)
    
    categories = Category.objects.all().order_by('category_name')
    brands = Brand.objects.all().order_by('brand_name')
    
    return render(request, 'main/admin/categories_list.html', {
        'categories': categories,
        'brands': brands
    })

@login_required
def admin_category_add(request):
    """Добавление категории админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        try:
            category = Category.objects.create(
                category_name=request.POST.get('category_name', '').strip(),
                category_description=request.POST.get('category_description', '').strip() or None,
                parent_category_id=request.POST.get('parent_category_id') or None
            )
            _log_activity(request.user, 'create', f'category_{category.id}', f'Создана категория: {category.category_name}', request)
            messages.success(request, 'Категория добавлена')
            return redirect('admin_categories_list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании категории: {str(e)}')
    
    categories = Category.objects.all()
    return render(request, 'main/admin/category_edit.html', {
        'category': None,
        'categories': categories
    })

@login_required
def admin_category_edit(request, category_id):
    """Редактирование категории админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    category = get_object_or_404(Category, pk=category_id)
    
    if request.method == 'POST':
        try:
            old_name = category.category_name
            category.category_name = request.POST.get('category_name', '').strip()
            category.category_description = request.POST.get('category_description', '').strip() or None
            category.parent_category_id = request.POST.get('parent_category_id') or None
            category.save()
            _log_activity(request.user, 'update', f'category_{category_id}', f'Обновлена категория: {old_name} -> {category.category_name}', request)
            messages.success(request, 'Категория обновлена')
            return redirect('admin_categories_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    categories = Category.objects.exclude(pk=category_id)
    return render(request, 'main/admin/category_edit.html', {
        'category': category,
        'categories': categories
    })

@login_required
def admin_brand_add(request):
    """Добавление бренда админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        try:
            brand = Brand.objects.create(
                brand_name=request.POST.get('brand_name', '').strip(),
                brand_country=request.POST.get('brand_country', '').strip() or None,
                brand_description=request.POST.get('brand_description', '').strip() or None
            )
            _log_activity(request.user, 'create', f'brand_{brand.id}', f'Создан бренд: {brand.brand_name}', request)
            messages.success(request, 'Бренд добавлен')
            return redirect('admin_categories_list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании бренда: {str(e)}')
    
    return render(request, 'main/admin/brand_edit.html', {'brand': None})

@login_required
def admin_brand_edit(request, brand_id):
    """Редактирование бренда админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    brand = get_object_or_404(Brand, pk=brand_id)
    
    if request.method == 'POST':
        try:
            old_name = brand.brand_name
            brand.brand_name = request.POST.get('brand_name', '').strip()
            brand.brand_country = request.POST.get('brand_country', '').strip() or None
            brand.brand_description = request.POST.get('brand_description', '').strip() or None
            brand.save()
            _log_activity(request.user, 'update', f'brand_{brand_id}', f'Обновлен бренд: {old_name} -> {brand.brand_name}', request)
            messages.success(request, 'Бренд обновлен')
            return redirect('admin_categories_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    return render(request, 'main/admin/brand_edit.html', {'brand': brand})

# =================== УПРАВЛЕНИЕ ПОСТАВЩИКАМИ ===================

@login_required
def admin_suppliers_list(request):
    """Список поставщиков для админа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'suppliers_list', 'Просмотр списка поставщиков', request)
    
    q = (request.GET.get('q') or '').strip()
    suppliers = Supplier.objects.all().order_by('supplier_name')
    
    if q:
        suppliers = suppliers.filter(
            Q(supplier_name__icontains=q) | 
            Q(contact_person__icontains=q) |
            Q(contact_email__icontains=q)
        )
    
    paginator = Paginator(suppliers, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'main/admin/suppliers_list.html', {
        'page_obj': page_obj,
        'q': q
    })

@login_required
def admin_supplier_add(request):
    """Добавление поставщика админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        try:
            supplier = Supplier.objects.create(
                supplier_name=request.POST.get('supplier_name', '').strip(),
                contact_person=request.POST.get('contact_person', '').strip() or None,
                contact_phone=request.POST.get('contact_phone', '').strip() or None,
                contact_email=request.POST.get('contact_email', '').strip() or None,
                supply_country=request.POST.get('supply_country', '').strip() or None,
                delivery_cost=Decimal(request.POST.get('delivery_cost', '0')) if request.POST.get('delivery_cost') else None,
                supplier_type=request.POST.get('supplier_type', '').strip() or None
            )
            _log_activity(request.user, 'create', f'supplier_{supplier.id}', f'Создан поставщик: {supplier.supplier_name}', request)
            messages.success(request, 'Поставщик добавлен')
            return redirect('admin_suppliers_list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании поставщика: {str(e)}')
    
    return render(request, 'main/admin/supplier_edit.html', {'supplier': None})

@login_required
def admin_supplier_edit(request, supplier_id):
    """Редактирование поставщика админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    if request.method == 'POST':
        try:
            old_name = supplier.supplier_name
            supplier.supplier_name = request.POST.get('supplier_name', '').strip()
            supplier.contact_person = request.POST.get('contact_person', '').strip() or None
            supplier.contact_phone = request.POST.get('contact_phone', '').strip() or None
            supplier.contact_email = request.POST.get('contact_email', '').strip() or None
            supplier.supply_country = request.POST.get('supply_country', '').strip() or None
            delivery_cost_str = request.POST.get('delivery_cost', '').strip()
            supplier.delivery_cost = Decimal(delivery_cost_str) if delivery_cost_str else None
            supplier.supplier_type = request.POST.get('supplier_type', '').strip() or None
            supplier.save()
            _log_activity(request.user, 'update', f'supplier_{supplier_id}', f'Обновлен поставщик: {old_name} -> {supplier.supplier_name}', request)
            messages.success(request, 'Поставщик обновлен')
            return redirect('admin_suppliers_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
    
    return render(request, 'main/admin/supplier_edit.html', {'supplier': supplier})

@login_required
def admin_supplier_delete(request, supplier_id):
    """Удаление поставщика админом"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    
    if request.method == 'POST':
        supplier_name = supplier.supplier_name
        supplier.delete()
        _log_activity(request.user, 'delete', f'supplier_{supplier_id}', f'Удален поставщик: {supplier_name}', request)
        messages.success(request, f'Поставщик {supplier_name} удален')
        return redirect('admin_suppliers_list')
    
    return render(request, 'main/admin/supplier_delete.html', {'supplier': supplier})

# =================== УПРАВЛЕНИЕ БЭКАПАМИ БАЗЫ ДАННЫХ ===================

@login_required
def admin_backups_list(request):
    """Список бэкапов базы данных"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    _log_activity(request.user, 'view', 'backups_list', 'Просмотр списка бэкапов', request)
    
    backups = DatabaseBackup.objects.all().order_by('-created_at')
    
    paginator = Paginator(backups, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'main/admin/backups_list.html', {
        'page_obj': page_obj
    })

@login_required
def admin_backup_create(request):
    """Создание бэкапа базы данных"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    if request.method == 'POST':
        try:
            from django.conf import settings
            import shutil
            from datetime import datetime
            import os
            
            # Получаем путь к базе данных
            db_path = settings.DATABASES['default']['NAME']
            if not os.path.exists(db_path):
                messages.error(request, 'База данных не найдена')
                return redirect('admin_backups_list')
            
            # Создаем директорию для бэкапов, если её нет
            backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Генерируем имя файла бэкапа
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'db_backup_{timestamp}.sqlite3'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Копируем файл базы данных
            shutil.copy2(db_path, backup_path)
            
            # Получаем размер файла
            file_size = os.path.getsize(backup_path)
            
            # Создаем запись в базе данных
            backup_name = request.POST.get('backup_name', '').strip() or f'Бэкап от {datetime.now().strftime("%d.%m.%Y %H:%M")}'
            schedule = request.POST.get('schedule', 'now')
            notes = request.POST.get('notes', '').strip() or None
            
            # Если выбрано "Прямо сейчас", создаем бэкап немедленно
            # Если выбрано расписание, сохраняем настройку для автоматических бэкапов
            is_automatic = schedule != 'now'
            
            backup = DatabaseBackup.objects.create(
                backup_name=backup_name,
                created_by=request.user,
                file_size=file_size,
                schedule=schedule,
                notes=notes,
                is_automatic=is_automatic
            )
            
            # Сохраняем путь к файлу
            backup.backup_file.name = f'backups/{backup_filename}'
            backup.save()
            
            _log_activity(request.user, 'create', f'backup_{backup.id}', f'Создан бэкап базы данных: {backup_name}', request)
            messages.success(request, f'Бэкап "{backup_name}" успешно создан')
            return redirect('admin_backups_list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании бэкапа: {str(e)}')
            return redirect('admin_backups_list')
    
    return render(request, 'main/admin/backup_create.html')

@login_required
def admin_backup_download(request, backup_id):
    """Скачивание бэкапа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    backup = get_object_or_404(DatabaseBackup, pk=backup_id)
    
    if not backup.backup_file:
        messages.error(request, 'Файл бэкапа не найден')
        return redirect('admin_backups_list')
    
    _log_activity(request.user, 'download', f'backup_{backup_id}', f'Скачан бэкап: {backup.backup_name}', request)
    
    from django.http import FileResponse
    import os
    from django.conf import settings
    
    file_path = os.path.join(settings.MEDIA_ROOT, backup.backup_file.name)
    if not os.path.exists(file_path):
        messages.error(request, 'Файл бэкапа не найден на сервере')
        return redirect('admin_backups_list')
    
    response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{backup.backup_name.replace(" ", "_")}.sqlite3"'
    return response

@login_required
def admin_backup_delete(request, backup_id):
    """Удаление бэкапа"""
    if not _user_is_admin(request.user):
        return redirect('profile')
    
    backup = get_object_or_404(DatabaseBackup, pk=backup_id)
    
    if request.method == 'POST':
        try:
            backup_name = backup.backup_name
            # Удаляем файл, если он существует
            if backup.backup_file:
                from django.conf import settings
                file_path = os.path.join(settings.MEDIA_ROOT, backup.backup_file.name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            backup.delete()
            _log_activity(request.user, 'delete', f'backup_{backup_id}', f'Удален бэкап: {backup_name}', request)
            messages.success(request, f'Бэкап "{backup_name}" удален')
            return redirect('admin_backups_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении бэкапа: {str(e)}')
    
    return render(request, 'main/admin/backup_delete.html', {'backup': backup})