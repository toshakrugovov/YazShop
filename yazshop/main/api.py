from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import (
    Role, UserProfile, UserAddress, Category, Brand, Supplier, Product, ProductSize,
    Tag, ProductTag, Favorite, Cart, CartItem, Order, OrderItem, Payment,
    Delivery, Promotion, ProductReview, SupportTicket, ActivityLog,
    SavedPaymentMethod, CardTransaction, BalanceTransaction, Receipt, ReceiptItem,
    OrganizationAccount, OrganizationTransaction
)
from .serializers import (
    RoleSerializer, UserProfileSerializer, UserAddressSerializer, CategorySerializer, BrandSerializer,
    SupplierSerializer, ProductSerializer, ProductSizeSerializer, TagSerializer, ProductTagSerializer,
    FavoriteSerializer, CartSerializer, CartItemSerializer, OrderSerializer, OrderItemSerializer,
    PaymentSerializer, DeliverySerializer, PromotionSerializer, ProductReviewSerializer,
    SupportTicketSerializer, ActivityLogSerializer, SavedPaymentMethodSerializer,
    CardTransactionSerializer, BalanceTransactionSerializer, ReceiptSerializer, ReceiptItemSerializer,
    OrganizationAccountSerializer, OrganizationTransactionSerializer
)
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from .helpers import _user_is_admin, _user_is_manager, _log_activity


# ===== Permissions =====
class ReadOnlyOrAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user and request.user.is_authenticated


# ===== ViewSets =====
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related('user', 'role').all()
    serializer_class = UserProfileSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class UserAddressViewSet(viewsets.ModelViewSet):
    queryset = UserAddress.objects.select_related('user').all()
    serializer_class = UserAddressSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category', 'brand', 'supplier').all()
    serializer_class = ProductSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class ProductSizeViewSet(viewsets.ModelViewSet):
    queryset = ProductSize.objects.select_related('product').all()
    serializer_class = ProductSizeSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class ProductTagViewSet(viewsets.ModelViewSet):
    queryset = ProductTag.objects.select_related('product', 'tag').all()
    serializer_class = ProductTagSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.select_related('user', 'product').all()
    serializer_class = FavoriteSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.select_related('user').all()
    serializer_class = CartSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.select_related('cart', 'product', 'size').all()
    serializer_class = CartItemSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('user', 'address').all()
    serializer_class = OrderSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.select_related('order', 'product', 'size').all()
    serializer_class = OrderItemSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('order').all()
    serializer_class = PaymentSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.select_related('order').all()
    serializer_class = DeliverySerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class ProductReviewViewSet(viewsets.ModelViewSet):
    queryset = ProductReview.objects.select_related('user', 'product').all()
    serializer_class = ProductReviewSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class SupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.select_related('user').all()
    serializer_class = SupportTicketSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


class ActivityLogViewSet(viewsets.ModelViewSet):
    queryset = ActivityLog.objects.select_related('user').all()
    serializer_class = ActivityLogSerializer
    permission_classes = [ReadOnlyOrAuthenticated]


# ===== API Views =====
@method_decorator(csrf_exempt, name='dispatch')
class CheckEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'exists': False, 'error': 'Email не указан'}, status=status.HTTP_400_BAD_REQUEST)
        exists = User.objects.filter(email=email).exists()
        return Response({'exists': exists})


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')

        if not email or not password:
            return Response({'success': False, 'error': 'Email и пароль обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            
            # Проверка, что пользователь активен (стандартное поле Django)
            if not user.is_active:
                return Response({
                    'success': False, 
                    'error': 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Проверка статуса в профиле
            try:
                profile = user.profile
                if profile.user_status == 'blocked':
                    return Response({
                        'success': False, 
                        'error': 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka'
                    }, status=status.HTTP_403_FORBIDDEN)
            except UserProfile.DoesNotExist:
                # Если профиля нет, создаем его (но это не должно происходить при входе)
                pass
            
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                # Повторная проверка после аутентификации
                if not user.is_active:
                    return Response({
                        'success': False, 
                        'error': 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                try:
                    profile = user.profile
                    if profile.user_status == 'blocked':
                        return Response({
                            'success': False, 
                            'error': 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka'
                        }, status=status.HTTP_403_FORBIDDEN)
                except UserProfile.DoesNotExist:
                    pass
                
                auth_login(request, user)
                return Response({
                    'success': True,
                    'message': 'Успешный вход',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    }
                })
            else:
                return Response({'success': False, 'error': 'Неверный пароль'}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Пользователь не найден'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            first_name = (request.data.get('first_name') or '').strip()
            last_name = (request.data.get('last_name') or '').strip()
            email = (request.data.get('email') or '').strip().lower()
            password = (request.data.get('password') or '').strip()
            password2 = (request.data.get('password2') or '').strip()
            phone_number = (request.data.get('phone_number') or '').strip()
            birth_date_str = (request.data.get('birth_date') or '').strip()
            secret_word = (request.data.get('secret_word') or '').strip()

            # Проверки
            if not (first_name and last_name and email and password and password2):
                return Response({'success': False, 'error': 'Заполните все обязательные поля'}, status=status.HTTP_400_BAD_REQUEST)
            if password != password2:
                return Response({'success': False, 'error': 'Пароли не совпадают'}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(email=email).exists():
                return Response({'success': False, 'error': 'Пользователь с таким email уже существует'}, status=status.HTTP_400_BAD_REQUEST)

            # Генерация уникального username
            username_base = email.split('@')[0]
            username = username_base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1

            # Создание пользователя
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Получаем роль USER (id=1)
            user_role = Role.objects.get(id=1)

            # Создаём профиль с full_name и ролью
            profile_kwargs = {
                'user': user,
                'role': user_role,
                'full_name': f"{first_name} {last_name}".strip()
            }
            if phone_number:
                profile_kwargs['phone_number'] = phone_number
            if birth_date_str:
                try:
                    profile_kwargs['birth_date'] = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                except Exception:
                    pass
            if secret_word:
                profile_kwargs['secret_word'] = secret_word

            UserProfile.objects.create(**profile_kwargs)

            return Response({'success': True, 'message': 'Регистрация успешна'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Восстановление пароля - проверяет все данные и устанавливает новый пароль"""
        try:
            import re
            phone = (request.data.get('phone') or '').strip()
            email = (request.data.get('email') or '').strip().lower()
            first_name = (request.data.get('first_name') or '').strip()
            last_name = (request.data.get('last_name') or '').strip()
            secret_word = (request.data.get('secret_word') or '').strip()
            new_password = (request.data.get('password') or '').strip()

            # Проверка обязательных полей
            if not (phone and email and first_name and last_name and secret_word and new_password):
                return Response({
                    'success': False,
                    'error': 'Заполните все поля, включая секретное слово'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Нормализация телефона
            normalized_phone = re.sub(r'\D', '', phone)
            if normalized_phone.startswith('8'):
                normalized_phone = '7' + normalized_phone[1:]
            if not normalized_phone.startswith('7') or len(normalized_phone) != 11:
                return Response({
                    'success': False,
                    'error': 'Неверный формат телефона'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Поиск пользователя
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Пользователь с таким email не найден'
                }, status=status.HTTP_404_NOT_FOUND)

            # Проверка профиля
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Профиль пользователя не найден'
                }, status=status.HTTP_404_NOT_FOUND)

            # Проверка всех данных пользователя
            if (user.first_name.strip().lower() != first_name.strip().lower() or
                user.last_name.strip().lower() != last_name.strip().lower()):
                return Response({
                    'success': False,
                    'error': 'Неверные данные пользователя'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверка телефона
            profile_phone_raw = profile.phone_number or ''
            profile_phone = re.sub(r'\D', '', profile_phone_raw)
            if profile_phone.startswith('8'):
                profile_phone = '7' + profile_phone[1:]
            if not profile_phone.startswith('7') or len(profile_phone) != 11:
                profile_phone_normalized = ''
            else:
                profile_phone_normalized = profile_phone

            if profile_phone_normalized != normalized_phone:
                return Response({
                    'success': False,
                    'error': 'Неверный номер телефона'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверка секретного слова (ДО проверки пароля!)
            if not profile.secret_word:
                return Response({
                    'success': False,
                    'error': 'Секретное слово не установлено. Обратитесь в поддержку: https://t.me/toshaplenka'
                }, status=status.HTTP_400_BAD_REQUEST)

            if profile.secret_word.strip().lower() != secret_word.strip().lower():
                return Response({
                    'success': False,
                    'error': 'Неверное секретное слово'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверка силы пароля (только если все предыдущие проверки прошли)
            if not (re.search(r'[A-ZА-Я]', new_password) and
                    re.search(r'[a-zа-я]', new_password) and
                    re.search(r'\d', new_password) and
                    len(new_password) >= 8):
                return Response({
                    'success': False,
                    'error': 'Пароль должен содержать минимум 8 символов, буквы верхнего и нижнего регистра и цифры'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Установка нового пароля
            user.set_password(new_password)
            user.save()

            return Response({
                'success': True,
                'message': 'Пароль успешно изменен'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при восстановлении пароля: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class VerifyResetDataView(APIView):
    """Проверка данных для восстановления пароля (без установки нового пароля)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            import re
            phone = (request.data.get('phone') or '').strip()
            email = (request.data.get('email') or '').strip().lower()
            first_name = (request.data.get('first_name') or '').strip()
            last_name = (request.data.get('last_name') or '').strip()
            secret_word = (request.data.get('secret_word') or '').strip()

            # Проверка обязательных полей
            if not (phone and email and first_name and last_name and secret_word):
                return Response({
                    'success': False,
                    'error': 'Заполните все поля, включая секретное слово'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Нормализация телефона
            normalized_phone = re.sub(r'\D', '', phone)
            if normalized_phone.startswith('8'):
                normalized_phone = '7' + normalized_phone[1:]
            if not normalized_phone.startswith('7') or len(normalized_phone) != 11:
                return Response({
                    'success': False,
                    'error': 'Неверный формат телефона'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Поиск пользователя
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Пользователь с таким email не найден'
                }, status=status.HTTP_404_NOT_FOUND)

            # Проверка профиля
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Профиль пользователя не найден'
                }, status=status.HTTP_404_NOT_FOUND)

            # Проверка всех данных пользователя
            if (user.first_name.strip().lower() != first_name.strip().lower() or
                user.last_name.strip().lower() != last_name.strip().lower()):
                return Response({
                    'success': False,
                    'error': 'Неверные имя или фамилия'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверка телефона
            profile_phone_raw = profile.phone_number or ''
            profile_phone = re.sub(r'\D', '', profile_phone_raw)
            if profile_phone.startswith('8'):
                profile_phone = '7' + profile_phone[1:]
            if not profile_phone.startswith('7') or len(profile_phone) != 11:
                profile_phone_normalized = ''
            else:
                profile_phone_normalized = profile_phone

            if profile_phone_normalized != normalized_phone:
                return Response({
                    'success': False,
                    'error': 'Неверный номер телефона'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверка секретного слова
            if not profile.secret_word:
                return Response({
                    'success': False,
                    'error': 'Секретное слово не установлено. Обратитесь в поддержку: https://t.me/toshaplenka'
                }, status=status.HTTP_400_BAD_REQUEST)

            if profile.secret_word.strip().lower() != secret_word.strip().lower():
                return Response({
                    'success': False,
                    'error': 'Неверное секретное слово'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Все проверки пройдены
            return Response({
                'success': True,
                'message': 'Данные проверены успешно'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при проверке данных: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== Permissions для API =====
class IsAdminOrReadOnly(permissions.BasePermission):
    """Только администратор может изменять"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return _user_is_admin(request.user)


class IsManagerOrReadOnly(permissions.BasePermission):
    """Менеджер или администратор может изменять"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return _user_is_manager(request.user)


# ===== API для профиля пользователя =====
@method_decorator(csrf_exempt, name='dispatch')
class ProfileAPIView(APIView):
    """API для работы с профилем пользователя"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить профиль текущего пользователя"""
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)

    def put(self, request):
        """Обновить профиль"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)

        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        phone_number = request.data.get('phone_number', '').strip()
        birth_date_str = request.data.get('birth_date', '').strip()
        secret_word = request.data.get('secret_word', '').strip()

        if not first_name or not last_name:
            return Response({
                'success': False,
                'error': 'Имя и Фамилия обязательны'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Обновляем User
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()

        # Обновляем профиль
        profile.phone_number = phone_number
        if birth_date_str:
            try:
                profile.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'Неверный формат даты рождения. Используйте ГГГГ-ММ-ДД.'
                }, status=status.HTTP_400_BAD_REQUEST)
        if secret_word:
            profile.secret_word = secret_word
        profile.save()

        serializer = UserProfileSerializer(profile)
        return Response({
            'success': True,
            'profile': serializer.data
        })


# ===== API для адресов =====
@method_decorator(csrf_exempt, name='dispatch')
class AddressAPIView(APIView):
    """API для работы с адресами пользователя"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить все адреса пользователя"""
        addresses = UserAddress.objects.filter(user=request.user)
        serializer = UserAddressSerializer(addresses, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Создать новый адрес"""
        address_title = request.data.get('address_title', '').strip()
        city_name = request.data.get('city_name', '').strip()
        street_name = request.data.get('street_name', '').strip()
        house_number = request.data.get('house_number', '').strip()
        apartment_number = request.data.get('apartment_number', '').strip()
        postal_code = request.data.get('postal_code', '').strip()
        is_primary = request.data.get('is_primary', False)

        if not all([city_name, street_name, house_number, postal_code]):
            return Response({
                'success': False,
                'error': 'Заполните все обязательные поля'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Если это основной адрес, снимаем флаг с других
        if is_primary:
            UserAddress.objects.filter(user=request.user).update(is_primary=False)

        address = UserAddress.objects.create(
            user=request.user,
            address_title=address_title or None,
            city_name=city_name,
            street_name=street_name,
            house_number=house_number,
            apartment_number=apartment_number or None,
            postal_code=postal_code,
            is_primary=is_primary
        )

        serializer = UserAddressSerializer(address)
        return Response({
            'success': True,
            'address': serializer.data
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class AddressDetailAPIView(APIView):
    """API для работы с конкретным адресом"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, address_id):
        """Получить адрес"""
        address = get_object_or_404(UserAddress, id=address_id, user=request.user)
        serializer = UserAddressSerializer(address)
        return Response(serializer.data)

    def put(self, request, address_id):
        """Обновить адрес"""
        address = get_object_or_404(UserAddress, id=address_id, user=request.user)
        
        address.address_title = request.data.get('address_title', address.address_title).strip() or None
        address.city_name = request.data.get('city_name', address.city_name).strip()
        address.street_name = request.data.get('street_name', address.street_name).strip()
        address.house_number = request.data.get('house_number', address.house_number).strip()
        address.apartment_number = request.data.get('apartment_number', address.apartment_number).strip() or None
        address.postal_code = request.data.get('postal_code', address.postal_code).strip()
        is_primary = request.data.get('is_primary', address.is_primary)

        if not all([address.city_name, address.street_name, address.house_number, address.postal_code]):
            return Response({
                'success': False,
                'error': 'Заполните все обязательные поля'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Если это основной адрес, снимаем флаг с других
        if is_primary:
            UserAddress.objects.filter(user=request.user).exclude(id=address_id).update(is_primary=False)
        
        address.is_primary = is_primary
        address.save()

        serializer = UserAddressSerializer(address)
        return Response({
            'success': True,
            'address': serializer.data
        })

    def delete(self, request, address_id):
        """Удалить адрес"""
        address = get_object_or_404(UserAddress, id=address_id, user=request.user)
        address.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


# ===== API для корзины =====
@method_decorator(csrf_exempt, name='dispatch')
class CartAPIView(APIView):
    """API для работы с корзиной"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить корзину пользователя"""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def post(self, request):
        """Добавить товар в корзину"""
        product_id = request.data.get('product_id')
        size_id = request.data.get('size_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            return Response({
                'success': False,
                'error': 'product_id обязателен'
            }, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id)
        
        if not product.is_available:
            return Response({
                'success': False,
                'error': 'Товар недоступен'
            }, status=status.HTTP_400_BAD_REQUEST)

        size = None
        if size_id:
            size = get_object_or_404(ProductSize, id=size_id, product=product)
            if size.size_stock < quantity:
                return Response({
                    'success': False,
                    'error': f'Недостаточно товара на складе. Доступно: {size.size_stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif product.stock_quantity < quantity:
            return Response({
                'success': False,
                'error': f'Недостаточно товара на складе. Доступно: {product.stock_quantity}'
            }, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        # Проверяем, есть ли уже такой товар с этим размером
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
            defaults={'unit_price': product.final_price, 'quantity': quantity}
        )

        if not created:
            new_quantity = item.quantity + quantity
            if size and size.size_stock < new_quantity:
                return Response({
                    'success': False,
                    'error': f'Недостаточно товара на складе. Доступно: {size.size_stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif not size and product.stock_quantity < new_quantity:
                return Response({
                    'success': False,
                    'error': f'Недостаточно товара на складе. Доступно: {product.stock_quantity}'
                }, status=status.HTTP_400_BAD_REQUEST)
            item.quantity = new_quantity
            item.save()

        cart_serializer = CartSerializer(cart)
        return Response({
            'success': True,
            'cart': cart_serializer.data
        })


@method_decorator(csrf_exempt, name='dispatch')
class CartItemAPIView(APIView):
    """API для работы с элементами корзины"""
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, item_id):
        """Обновить количество товара в корзине"""
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        new_quantity = int(request.data.get('quantity', 1))

        if new_quantity <= 0:
            return Response({
                'success': False,
                'error': 'Количество должно быть больше нуля'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Проверка количества на складе
        if item.size:
            if item.size.size_stock < new_quantity:
                return Response({
                    'success': False,
                    'error': f'Недостаточно товара на складе. Доступно: {item.size.size_stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif item.product.stock_quantity < new_quantity:
            return Response({
                'success': False,
                'error': f'Недостаточно товара на складе. Доступно: {item.product.stock_quantity}'
            }, status=status.HTTP_400_BAD_REQUEST)

        item.quantity = new_quantity
        item.save()

        cart_serializer = CartSerializer(item.cart)
        return Response({
            'success': True,
            'cart': cart_serializer.data
        })

    def delete(self, request, item_id):
        """Удалить товар из корзины"""
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        item.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


# ===== API для заказов =====
@method_decorator(csrf_exempt, name='dispatch')
class OrderAPIView(APIView):
    """API для работы с заказами"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить все заказы пользователя"""
        orders = Order.objects.filter(user=request.user).select_related('address').order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Создать новый заказ (оформление заказа)"""
        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            return Response({
                'success': False,
                'error': 'Корзина пуста'
            }, status=status.HTTP_400_BAD_REQUEST)

        address_id = request.data.get('address_id')
        saved_payment_id = request.data.get('saved_payment_id')
        promo_code = request.data.get('promo_code', '').strip()
        payment_method = request.data.get('payment_method', 'cash')
        
        # Данные новой карты (если не используется сохраненная)
        card_number = request.data.get('card_number', '').strip()
        card_holder_name = request.data.get('card_holder_name', '').strip()
        expiry_month = request.data.get('expiry_month', '').strip()
        expiry_year = request.data.get('expiry_year', '').strip()
        save_card = request.data.get('save_card', False)

        if not address_id:
            return Response({
                'success': False,
                'error': 'Выберите адрес доставки'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Проверка количества товара на складе
        errors = []
        for item in cart.items.all():
            if item.size:
                if item.size.size_stock < item.quantity:
                    errors.append(f"Товар '{item.product.product_name}' размера {item.size.size_label}: недостаточно на складе (доступно: {item.size.size_stock}, запрошено: {item.quantity})")
            elif item.product.stock_quantity < item.quantity:
                errors.append(f"Товар '{item.product.product_name}': недостаточно на складе (доступно: {item.product.stock_quantity}, запрошено: {item.quantity})")
        
        if errors:
            return Response({
                'success': False,
                'error': '; '.join(errors)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Проверка промокода
        promo = None
        discount_amount = Decimal('0')
        if promo_code:
            try:
                promo = Promotion.objects.get(promo_code=promo_code.upper(), is_active=True)
                today = timezone.now().date()
                if promo.start_date and promo.start_date > today:
                    return Response({
                        'success': False,
                        'error': 'Промокод еще не действует'
                    }, status=status.HTTP_400_BAD_REQUEST)
                if promo.end_date and promo.end_date < today:
                    return Response({
                        'success': False,
                        'error': 'Промокод истек'
                    }, status=status.HTTP_400_BAD_REQUEST)
                cart_total = cart.total_price()
                discount_amount = cart_total * (promo.discount / Decimal('100'))
            except Promotion.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Неверный промокод'
                }, status=status.HTTP_400_BAD_REQUEST)

        try:
            address = UserAddress.objects.get(id=address_id, user=request.user)
        except UserAddress.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Адрес не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Вычисляем итоговую сумму
        cart_total = cart.total_price()
        delivery_cost = Decimal('1000.00')
        subtotal_after_discount = cart_total - discount_amount
        pre_vat_amount = subtotal_after_discount + delivery_cost
        vat_rate = Decimal('20.00')
        vat_amount = (pre_vat_amount * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
        amount_after_vat = pre_vat_amount + vat_amount
        tax_rate = Decimal('13.00')
        tax_amount = (amount_after_vat * tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        final_amount = amount_after_vat.quantize(Decimal('0.01'))

        # Проверяем способ оплаты
        paid_from_balance = False
        if payment_method == 'balance':
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if profile.balance < final_amount:
                return Response({
                    'success': False,
                    'error': f'Недостаточно средств на балансе. Текущий баланс: {profile.balance} ₽, требуется: {final_amount} ₽'
                }, status=status.HTTP_400_BAD_REQUEST)
            paid_from_balance = True

        # Вся логика оформления в транзакции
        try:
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
                    
                    profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
                    if profile.balance < final_amount:
                        return Response({
                            'success': False,
                            'error': f'Недостаточно средств на балансе. Текущий баланс: {profile.balance} ₽, требуется: {final_amount} ₽'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    balance_before = profile.balance
                    profile.balance -= final_amount
                    profile.save()
                    
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
                    if saved_payment_id and saved_payment_id != '':
                        saved_payment = SavedPaymentMethod.objects.select_for_update().get(id=saved_payment_id, user=request.user)
                        payment_method_type = saved_payment.card_type or 'card'
                        if saved_payment.balance < final_amount:
                            return Response({
                                'success': False,
                                'error': f'Недостаточно средств на выбранной карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        new_card_balance = saved_payment.balance - final_amount
                        if new_card_balance < 0:
                            return Response({
                                'success': False,
                                'error': f'Недостаточно средств на выбранной карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        saved_payment.balance = new_card_balance
                        saved_payment.save()
                        CardTransaction.objects.create(
                            saved_payment_method=saved_payment,
                            transaction_type='withdrawal',
                            amount=final_amount,
                            description=f'Оплата заказа #{order.id}',
                            status='completed'
                        )
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
                                return Response({
                                    'success': False,
                                    'error': f'Недостаточно средств на карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽'
                                }, status=status.HTTP_400_BAD_REQUEST)
                            new_card_balance = saved_payment.balance - final_amount
                            if new_card_balance < 0:
                                return Response({
                                    'success': False,
                                    'error': f'Недостаточно средств на карте. Баланс карты: {saved_payment.balance} ₽, требуется: {final_amount} ₽'
                                }, status=status.HTTP_400_BAD_REQUEST)
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
                            return Response({
                                'success': False,
                                'error': 'Для оплаты новой картой сначала сохраните карту и убедитесь в наличии средств'
                            }, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({
                            'success': False,
                            'error': 'Выберите или введите данные карты'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Создаем запись о платеже
                payment = Payment.objects.create(
                    order=order,
                    payment_method=payment_method_type,
                    payment_amount=final_amount,
                    payment_status=payment_status,
                    saved_payment_method=saved_payment,
                    promo_code=promo
                )

                if payment_status == 'paid' and order.order_status != 'paid':
                    order.order_status = 'paid'
                    order.save(update_fields=['order_status'])
                
                # Переводим средства на счет организации (если платеж прошел, но не наличными)
                if payment_status == 'paid' and payment_method != 'cash':
                    org_account = OrganizationAccount.get_account()
                    balance_before = org_account.balance
                    tax_reserve_before = org_account.tax_reserve
                    
                    org_account.balance += final_amount
                    org_account.tax_reserve += tax_amount
                    org_account.save()
                    
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
                for item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        size=item.size,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                    
                    if item.size:
                        item.size.size_stock -= item.quantity
                        item.size.save()
                        item.product.stock_quantity -= item.quantity
                        item.product.save()
                    else:
                        item.product.stock_quantity -= item.quantity
                        item.product.save()
                
                cart.items.all().delete()

                # Формируем чек
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
                
                ReceiptItem.objects.create(
                    receipt=receipt,
                    product_name='Доставка',
                    article='DELIVERY',
                    quantity=1,
                    unit_price=delivery_cost,
                    line_total=delivery_cost,
                    vat_amount=delivery_vat
                )
                
                receipt.total_amount = final_amount.quantize(Decimal('0.01'))
                receipt.save()
                
                _log_activity(request.user, 'create', f'order_{order.id}', f'Создан заказ на сумму {final_amount} ₽', request)
                
                serializer = OrderSerializer(order)
                return Response({
                    'success': True,
                    'order': serializer.data,
                    'order_id': order.id
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при создании заказа: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDetailAPIView(APIView):
    """API для работы с конкретным заказом"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        """Получить заказ"""
        order = get_object_or_404(Order, id=order_id, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def post(self, request, order_id):
        """Отменить заказ"""
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if not order.can_be_cancelled:
            return Response({
                'success': False,
                'error': 'Заказ нельзя отменить'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Логика отмены заказа (из views.py cancel_order)
                order.order_status = 'cancelled'
                order.can_be_cancelled = False
                order.save()

                # Возвращаем товары на склад
                for item in order.items.all():
                    if item.size:
                        item.size.size_stock += item.quantity
                        item.size.save()
                    item.product.stock_quantity += item.quantity
                    item.product.save()

                # Возвращаем средства (если заказ был оплачен)
                was_paid = order.paid_from_balance or (order.payment_set.filter(payment_status='paid').exists())
                
                if was_paid:
                    # Дебит со счета организации
                    org_account = OrganizationAccount.objects.select_for_update().get(pk=1)
                    balance_before = org_account.balance
                    tax_reserve_before = org_account.tax_reserve
                    
                    org_account.balance -= order.total_amount
                    org_account.tax_reserve -= order.tax_amount
                    org_account.save()
                    
                    OrganizationTransaction.objects.create(
                        organization_account=org_account,
                        transaction_type='order_refund',
                        amount=order.total_amount,
                        description=f'Возврат средств по заказу #{order.id}',
                        order=order,
                        created_by=request.user,
                        balance_before=balance_before,
                        balance_after=org_account.balance,
                        tax_reserve_before=tax_reserve_before,
                        tax_reserve_after=org_account.tax_reserve
                    )

                    # Возврат средств пользователю
                    if order.paid_from_balance:
                        profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
                        balance_before = profile.balance
                        profile.balance += order.total_amount
                        profile.save()
                        
                        BalanceTransaction.objects.create(
                            user=request.user,
                            transaction_type='refund',
                            amount=order.total_amount,
                            balance_before=balance_before,
                            balance_after=profile.balance,
                            description=f'Возврат средств по заказу #{order.id}',
                            order=order,
                            status='completed'
                        )
                    else:
                        # Возврат на карту
                        payment = order.payment_set.filter(payment_status='paid').first()
                        if payment and payment.saved_payment_method:
                            card = payment.saved_payment_method
                            card.balance += order.total_amount
                            card.save()
                            
                            CardTransaction.objects.create(
                                saved_payment_method=card,
                                transaction_type='deposit',
                                amount=order.total_amount,
                                description=f'Возврат средств по заказу #{order.id}',
                                status='completed'
                            )

                _log_activity(request.user, 'update', f'order_{order.id}', 'Заказ отменен пользователем', request)
                
                serializer = OrderSerializer(order)
                return Response({
                    'success': True,
                    'order': serializer.data
                })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при отмене заказа: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== API для карт и платежей =====
@method_decorator(csrf_exempt, name='dispatch')
class PaymentMethodAPIView(APIView):
    """API для работы с сохраненными способами оплаты"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить все сохраненные карты пользователя"""
        cards = SavedPaymentMethod.objects.filter(user=request.user)
        serializer = SavedPaymentMethodSerializer(cards, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Добавить новую карту"""
        card_number = request.data.get('card_number', '').strip()
        card_holder_name = request.data.get('card_holder_name', '').strip()
        expiry_month = request.data.get('expiry_month', '').strip()
        expiry_year = request.data.get('expiry_year', '').strip()

        if not all([card_number, card_holder_name, expiry_month, expiry_year]):
            return Response({
                'success': False,
                'error': 'Заполните все поля карты'
            }, status=status.HTTP_400_BAD_REQUEST)

        card_type = 'visa' if card_number.startswith('4') else 'mastercard' if card_number.startswith('5') else 'card'
        card_last_4 = card_number[-4:] if len(card_number) >= 4 else card_number
        is_default = not SavedPaymentMethod.objects.filter(user=request.user).exists()

        card = SavedPaymentMethod.objects.create(
            user=request.user,
            card_number=card_last_4,
            card_holder_name=card_holder_name,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            card_type=card_type,
            is_default=is_default
        )

        serializer = SavedPaymentMethodSerializer(card)
        return Response({
            'success': True,
            'card': serializer.data
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentMethodDetailAPIView(APIView):
    """API для работы с конкретной картой"""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, card_id):
        """Удалить карту"""
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        card.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)

    def post(self, request, card_id):
        """Установить карту как основную"""
        SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
        card = get_object_or_404(SavedPaymentMethod, id=card_id, user=request.user)
        card.is_default = True
        card.save()
        serializer = SavedPaymentMethodSerializer(card)
        return Response({
            'success': True,
            'card': serializer.data
        })


# ===== API для баланса =====
@method_decorator(csrf_exempt, name='dispatch')
class BalanceAPIView(APIView):
    """API для работы с балансом пользователя"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить баланс и транзакции"""
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        transactions = BalanceTransaction.objects.filter(user=request.user).order_by('-created_at')[:20]
        
        return Response({
            'balance': str(profile.balance),
            'transactions': BalanceTransactionSerializer(transactions, many=True).data
        })

    def post(self, request):
        """Пополнить баланс с карты"""
        card_id = request.data.get('card_id')
        amount_str = request.data.get('amount', '0')

        if not card_id:
            return Response({
                'success': False,
                'error': 'Выберите карту'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(amount_str)
        except (ValueError, InvalidOperation):
            return Response({
                'success': False,
                'error': 'Неверная сумма'
            }, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({
                'success': False,
                'error': 'Сумма должна быть больше нуля'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            card = SavedPaymentMethod.objects.select_for_update().get(id=card_id, user=request.user)
            if card.balance < amount:
                return Response({
                    'success': False,
                    'error': f'Недостаточно средств на карте. Баланс карты: {card.balance} ₽'
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                card.balance -= amount
                card.save()

                profile, _ = UserProfile.objects.select_for_update().get_or_create(user=request.user)
                balance_before = profile.balance
                profile.balance += amount
                profile.save()

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
                    transaction_type='withdrawal',
                    amount=amount,
                    description='Пополнение баланса пользователя',
                    status='completed'
                )

            return Response({
                'success': True,
                'balance': str(profile.balance),
                'message': f'Баланс пополнен на {amount} ₽'
            })
        except SavedPaymentMethod.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Карта не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при пополнении баланса: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== API для валидации промокода =====
@method_decorator(csrf_exempt, name='dispatch')
class ValidatePromoAPIView(APIView):
    """API для валидации промокода"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Проверить промокод"""
        promo_code = request.data.get('promo_code', '').strip().upper()
        cart_total_str = request.data.get('cart_total', '0')

        if not promo_code:
            return Response({
                'success': False,
                'error': 'Введите промокод'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_total = Decimal(cart_total_str)
        except (ValueError, InvalidOperation):
            cart_total = Decimal('0')

        try:
            promo = Promotion.objects.get(promo_code=promo_code, is_active=True)
            today = timezone.now().date()
            
            if promo.start_date and promo.start_date > today:
                return Response({
                    'success': False,
                    'error': 'Промокод еще не действует'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if promo.end_date and promo.end_date < today:
                return Response({
                    'success': False,
                    'error': 'Промокод истек'
                }, status=status.HTTP_400_BAD_REQUEST)

            discount_amount = cart_total * (promo.discount / Decimal('100'))
            delivery_cost = Decimal('1000.00')
            subtotal_after_discount = cart_total - discount_amount
            pre_vat_amount = subtotal_after_discount + delivery_cost
            vat_rate = Decimal('20.00')
            vat_amount = (pre_vat_amount * vat_rate / Decimal('100')).quantize(Decimal('0.01'))
            total_with_vat = pre_vat_amount + vat_amount

            return Response({
                'success': True,
                'discount': str(discount_amount),
                'discount_percent': str(promo.discount),
                'subtotal': str(subtotal_after_discount),
                'delivery': str(delivery_cost),
                'vat_amount': str(vat_amount),
                'total': str(total_with_vat)
            })
        except Promotion.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Неверный промокод'
            }, status=status.HTTP_404_NOT_FOUND)


# ===== API для управления товарами (Менеджер/Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class ProductManagementAPIView(APIView):
    """API для управления товарами (только для менеджеров и админов)"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request):
        """Получить список товаров с фильтрацией"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        q = request.GET.get('q', '').strip()
        category_id = request.GET.get('category')
        brand_id = request.GET.get('brand')
        available_filter = request.GET.get('available')
        page = int(request.GET.get('page', 1))

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
        page_obj = paginator.get_page(page)

        serializer = ProductSerializer(page_obj.object_list, many=True)
        return Response({
            'success': True,
            'products': serializer.data,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })

    def post(self, request):
        """Создать новый товар"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            product = Product.objects.create(
                product_name=request.data.get('product_name', '').strip(),
                product_description=request.data.get('product_description', '').strip(),
                price=Decimal(request.data.get('price', '0')),
                discount=Decimal(request.data.get('discount', '0')),
                stock_quantity=int(request.data.get('stock_quantity', '0')),
                category_id=request.data.get('category_id') or None,
                brand_id=request.data.get('brand_id') or None,
                supplier_id=request.data.get('supplier_id') or None,
                main_image_url=request.data.get('main_image_url', '').strip() or None,
                image_url_1=request.data.get('image_url_1', '').strip() or None,
                image_url_2=request.data.get('image_url_2', '').strip() or None,
                image_url_3=request.data.get('image_url_3', '').strip() or None,
                image_url_4=request.data.get('image_url_4', '').strip() or None,
                is_available=request.data.get('is_available', False) and int(request.data.get('stock_quantity', '0')) > 0
            )

            # Добавляем размеры
            sizes_data = request.data.get('sizes', [])
            if isinstance(sizes_data, str):
                import json
                sizes_data = json.loads(sizes_data)
            for size_data in sizes_data:
                if size_data.get('size_label'):
                    ProductSize.objects.create(
                        product=product,
                        size_label=size_data.get('size_label').strip(),
                        size_stock=int(size_data.get('size_stock', '0'))
                    )

            # Добавляем теги
            tag_ids = request.data.get('tags', [])
            if isinstance(tag_ids, str):
                import json
                tag_ids = json.loads(tag_ids)
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.get_or_create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass

            _log_activity(request.user, 'create', f'product_{product.id}', f'Создан товар: {product.product_name}', request)
            serializer = ProductSerializer(product)
            return Response({
                'success': True,
                'product': serializer.data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при создании товара: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ProductManagementDetailAPIView(APIView):
    """API для работы с конкретным товаром"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request, product_id):
        """Получить товар"""
        product = get_object_or_404(Product, id=product_id)
        serializer = ProductSerializer(product)
        return Response(serializer.data)

    def put(self, request, product_id):
        """Обновить товар"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        product = get_object_or_404(Product, id=product_id)

        try:
            product.product_name = request.data.get('product_name', product.product_name).strip()
            product.product_description = request.data.get('product_description', product.product_description).strip()
            product.price = Decimal(request.data.get('price', product.price))
            product.discount = Decimal(request.data.get('discount', product.discount))
            stock_qty = int(request.data.get('stock_quantity', product.stock_quantity))
            product.stock_quantity = stock_qty
            product.category_id = request.data.get('category_id') or None
            product.brand_id = request.data.get('brand_id') or None
            product.supplier_id = request.data.get('supplier_id') or None
            product.main_image_url = request.data.get('main_image_url', '').strip() or None
            product.image_url_1 = request.data.get('image_url_1', '').strip() or None
            product.image_url_2 = request.data.get('image_url_2', '').strip() or None
            product.image_url_3 = request.data.get('image_url_3', '').strip() or None
            product.image_url_4 = request.data.get('image_url_4', '').strip() or None
            is_available_param = request.data.get('is_available', product.is_available)
            if stock_qty <= 0:
                is_available_param = False
            product.is_available = is_available_param
            product.save()

            # Обновляем размеры
            sizes_data = request.data.get('sizes', [])
            if isinstance(sizes_data, str):
                import json
                sizes_data = json.loads(sizes_data)
            
            existing_sizes = {s.id: s for s in product.sizes.all()}
            submitted_ids = [s.get('id') for s in sizes_data if s.get('id')]
            
            # Удаляем размеры, которых нет в запросе
            for size_id, size in existing_sizes.items():
                if size_id not in submitted_ids:
                    size.delete()

            # Обновляем или создаем размеры
            for size_data in sizes_data:
                size_id = size_data.get('id')
                if size_data.get('size_label'):
                    if size_id:
                        try:
                            size = ProductSize.objects.get(pk=size_id, product=product)
                            size.size_label = size_data.get('size_label').strip()
                            size.size_stock = int(size_data.get('size_stock', '0'))
                            size.save()
                        except ProductSize.DoesNotExist:
                            pass
                    else:
                        ProductSize.objects.create(
                            product=product,
                            size_label=size_data.get('size_label').strip(),
                            size_stock=int(size_data.get('size_stock', '0'))
                        )

            # Обновляем теги
            ProductTag.objects.filter(product=product).delete()
            tag_ids = request.data.get('tags', [])
            if isinstance(tag_ids, str):
                import json
                tag_ids = json.loads(tag_ids)
            for tag_id in tag_ids:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    ProductTag.objects.create(product=product, tag=tag)
                except Tag.DoesNotExist:
                    pass

            _log_activity(request.user, 'update', f'product_{product_id}', f'Обновлен товар: {product.product_name}', request)
            serializer = ProductSerializer(product)
            return Response({
                'success': True,
                'product': serializer.data
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при обновлении товара: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, product_id):
        """Удалить товар"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        product = get_object_or_404(Product, id=product_id)
        product_name = product.product_name
        product_id_val = product.id
        product.delete()
        _log_activity(request.user, 'delete', f'product_{product_id_val}', f'Удален товар: {product_name}', request)
        return Response({
            'success': True,
            'message': f'Товар "{product_name}" удален'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для управления категориями и брендами =====
@method_decorator(csrf_exempt, name='dispatch')
class CategoryManagementAPIView(APIView):
    """API для управления категориями"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request):
        """Получить все категории"""
        categories = Category.objects.all().order_by('category_name')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Создать категорию"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        category_name = request.data.get('category_name', '').strip()
        if not category_name:
            return Response({
                'success': False,
                'error': 'Название категории обязательно'
            }, status=status.HTTP_400_BAD_REQUEST)

        category = Category.objects.create(category_name=category_name)
        _log_activity(request.user, 'create', f'category_{category.id}', f'Создана категория: {category.category_name}', request)
        serializer = CategorySerializer(category)
        return Response({
            'success': True,
            'category': serializer.data
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class CategoryManagementDetailAPIView(APIView):
    """API для работы с конкретной категорией"""
    permission_classes = [IsManagerOrReadOnly]

    def put(self, request, category_id):
        """Обновить категорию"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        category = get_object_or_404(Category, id=category_id)
        old_name = category.category_name
        category.category_name = request.data.get('category_name', category.category_name).strip()
        category.save()
        _log_activity(request.user, 'update', f'category_{category_id}', f'Обновлена категория: {old_name} -> {category.category_name}', request)
        serializer = CategorySerializer(category)
        return Response({
            'success': True,
            'category': serializer.data
        })


@method_decorator(csrf_exempt, name='dispatch')
class BrandManagementAPIView(APIView):
    """API для управления брендами"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request):
        """Получить все бренды"""
        brands = Brand.objects.all().order_by('brand_name')
        serializer = BrandSerializer(brands, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Создать бренд"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        brand_name = request.data.get('brand_name', '').strip()
        if not brand_name:
            return Response({
                'success': False,
                'error': 'Название бренда обязательно'
            }, status=status.HTTP_400_BAD_REQUEST)

        brand = Brand.objects.create(brand_name=brand_name)
        _log_activity(request.user, 'create', f'brand_{brand.id}', f'Создан бренд: {brand.brand_name}', request)
        serializer = BrandSerializer(brand)
        return Response({
            'success': True,
            'brand': serializer.data
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class BrandManagementDetailAPIView(APIView):
    """API для работы с конкретным брендом"""
    permission_classes = [IsManagerOrReadOnly]

    def put(self, request, brand_id):
        """Обновить бренд"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        brand = get_object_or_404(Brand, id=brand_id)
        old_name = brand.brand_name
        brand.brand_name = request.data.get('brand_name', brand.brand_name).strip()
        brand.save()
        _log_activity(request.user, 'update', f'brand_{brand_id}', f'Обновлен бренд: {old_name} -> {brand.brand_name}', request)
        serializer = BrandSerializer(brand)
        return Response({
            'success': True,
            'brand': serializer.data
        })


# ===== API для управления заказами (Менеджер/Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class OrderManagementAPIView(APIView):
    """API для управления заказами"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request):
        """Получить список заказов с фильтрацией"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.GET.get('status')
        page = int(request.GET.get('page', 1))

        qs = Order.objects.select_related('user', 'address').prefetch_related('items').all()

        if status_filter:
            qs = qs.filter(order_status=status_filter)

        qs = qs.order_by('-created_at')
        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(page)

        serializer = OrderSerializer(page_obj.object_list, many=True)
        return Response({
            'success': True,
            'orders': serializer.data,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })


@method_decorator(csrf_exempt, name='dispatch')
class OrderManagementDetailAPIView(APIView):
    """API для работы с конкретным заказом"""
    permission_classes = [IsManagerOrReadOnly]

    def get(self, request, order_id):
        """Получить заказ"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, id=order_id)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def post(self, request, order_id):
        """Изменить статус заказа"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, id=order_id)
        new_status = request.data.get('status', '').strip()

        if new_status not in dict(Order.ORDER_STATUSES):
            return Response({
                'success': False,
                'error': 'Неверный статус заказа'
            }, status=status.HTTP_400_BAD_REQUEST)

        old_status = order.order_status
        order.order_status = new_status
        order.save()

        # Назначение курьера
        carrier_name = request.data.get('carrier_name', '').strip()
        if carrier_name:
            delivery, created = Delivery.objects.get_or_create(order=order)
            delivery.carrier_name = carrier_name
            delivery.save()

        _log_activity(request.user, 'update', f'order_{order_id}', f'Изменен статус заказа: {old_status} -> {new_status}', request)
        serializer = OrderSerializer(order)
        return Response({
            'success': True,
            'order': serializer.data
        })


# ===== API для управления пользователями (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class UserManagementAPIView(APIView):
    """API для управления пользователями (только для админов)"""
    permission_classes = [IsAdminOrReadOnly]

    def post(self, request):
        """Создать нового пользователя"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен. Требуется роль администратора'
            }, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username', '').strip()
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '').strip()
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        role_id = request.data.get('role_id')
        user_status = request.data.get('user_status', 'active')
        secret_word = request.data.get('secret_word', '').strip()

        if not username or not email or not password:
            return Response({
                'success': False,
                'error': 'Логин, email и пароль обязательны'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, не существует ли уже пользователь с таким username или email
        if User.objects.filter(username=username).exists():
            return Response({
                'success': False,
                'error': 'Пользователь с таким логином уже существует'
            }, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'Пользователь с таким email уже существует'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Создаем пользователя
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Создаем профиль
            profile = UserProfile.objects.create(
                user=user,
                role_id=role_id if role_id else None,
                user_status=user_status,
                full_name=f"{first_name} {last_name}".strip(),
                secret_word=secret_word if secret_word else None
            )

            _log_activity(request.user, 'create', f'user_{user.id}', f'Создан пользователь: {username}', request)

            return Response({
                'success': True,
                'user_id': user.id,
                'message': f'Пользователь {username} успешно создан'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при создании пользователя: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """Получить список пользователей с фильтрацией"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен. Требуется роль администратора'
            }, status=status.HTTP_403_FORBIDDEN)

        q = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status')
        role_filter = request.GET.get('role')
        activity_filter = request.GET.get('activity')
        page = int(request.GET.get('page', 1))

        qs = User.objects.select_related('profile').all().order_by('-date_joined')

        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        if status_filter:
            qs = qs.filter(profile__user_status=status_filter)
        if role_filter:
            qs = qs.filter(profile__role_id=role_filter)
        if activity_filter == 'active':
            month_ago = timezone.now() - timedelta(days=30)
            qs = qs.filter(order__created_at__gte=month_ago).distinct()
        elif activity_filter == 'inactive':
            month_ago = timezone.now() - timedelta(days=30)
            qs = qs.exclude(order__created_at__gte=month_ago).distinct()

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(page)

        users_data = []
        for user in page_obj.object_list:
            try:
                profile = user.profile
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'date_joined': user.date_joined,
                    'is_active': user.is_active,
                    'profile': {
                        'user_status': profile.user_status,
                        'role': profile.role.role_name if profile.role else None,
                        'phone_number': profile.phone_number,
                        'balance': str(profile.balance)
                    }
                })
            except UserProfile.DoesNotExist:
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'date_joined': user.date_joined,
                    'is_active': user.is_active,
                    'profile': None
                })

        return Response({
            'success': True,
            'users': users_data,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })


@method_decorator(csrf_exempt, name='dispatch')
class UserManagementDetailAPIView(APIView):
    """API для работы с конкретным пользователем"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, user_id):
        """Получить пользователя"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)
        try:
            profile = user.profile
            role_name = profile.role.role_name if profile.role else None
        except UserProfile.DoesNotExist:
            profile = None
            role_name = None

        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
                'is_active': user.is_active,
                'profile': {
                    'user_status': profile.user_status if profile else 'active',
                    'role': role_name,
                    'phone_number': profile.phone_number if profile else None,
                    'balance': str(profile.balance) if profile else '0.00'
                }
            }
        })

    def put(self, request, user_id):
        """Обновить пользователя"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)
        profile, _ = UserProfile.objects.get_or_create(user=user)

        # Обновление данных пользователя
        if 'first_name' in request.data:
            user.first_name = request.data.get('first_name', '').strip()
        if 'last_name' in request.data:
            user.last_name = request.data.get('last_name', '').strip()
        if 'email' in request.data:
            user.email = request.data.get('email', '').strip()
        if 'is_active' in request.data:
            user.is_active = request.data.get('is_active', True)
        user.save()

        # Обновление профиля
        if 'user_status' in request.data:
            old_status = profile.user_status
            profile.user_status = request.data.get('user_status', 'active')
            # Синхронизируем is_active с user_status
            if profile.user_status == 'blocked':
                user.is_active = False
                user.save()
            elif profile.user_status == 'active':
                user.is_active = True
                user.save()
            profile.save()
            _log_activity(request.user, 'update', f'user_{user_id}', f'Изменен статус: {old_status} -> {profile.user_status}', request)

        if 'role_id' in request.data:
            role_id = request.data.get('role_id')
            old_role = profile.role.role_name if profile.role else None
            if role_id:
                try:
                    role = Role.objects.get(id=role_id)
                    profile.role = role
                    profile.save()
                    new_role = role.role_name
                    _log_activity(request.user, 'update', f'user_{user_id}', f'Изменена роль: {old_role} -> {new_role}', request)
                except Role.DoesNotExist:
                    pass
            else:
                profile.role = None
                profile.save()

        _log_activity(request.user, 'update', f'user_{user_id}', f'Обновлен пользователь: {user.username}', request)

        return Response({
            'success': True,
            'message': 'Пользователь обновлен'
        })

    def post(self, request, user_id):
        """Блокировка/разблокировка пользователя"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)
        profile, _ = UserProfile.objects.get_or_create(user=user)

        old_status = profile.user_status
        if old_status == 'blocked':
            profile.user_status = 'active'
            user.is_active = True
        else:
            profile.user_status = 'blocked'
            user.is_active = False

        user.save()
        profile.save()

        _log_activity(request.user, 'update', f'user_{user_id}', f'Изменен статус пользователя: {old_status} -> {profile.user_status}', request)

        return Response({
            'success': True,
            'user_status': profile.user_status,
            'message': f'Пользователь {"заблокирован" if profile.user_status == "blocked" else "разблокирован"}'
        })

    def delete(self, request, user_id):
        """Удалить пользователя"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, id=user_id)
        username = user.username
        user_id_val = user.id
        user.delete()
        _log_activity(request.user, 'delete', f'user_{user_id_val}', f'Удален пользователь: {username}', request)
        return Response({
            'success': True,
            'message': f'Пользователь {username} удален'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для поддержки =====
@method_decorator(csrf_exempt, name='dispatch')
class SupportTicketAPIView(APIView):
    """API для работы с обращениями в поддержку"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить все обращения пользователя или все (для менеджеров)"""
        if _user_is_manager(request.user):
            # Менеджеры видят все обращения
            tickets = SupportTicket.objects.select_related('user').all().order_by('-created_at')
        else:
            # Пользователи видят только свои
            tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')

        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Создать новое обращение"""
        subject = request.data.get('subject', '').strip()
        message_text = request.data.get('message_text', '').strip()

        if not subject or not message_text:
            return Response({
                'success': False,
                'error': 'Заполните тему и сообщение'
            }, status=status.HTTP_400_BAD_REQUEST)

        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            message_text=message_text,
            ticket_status='new'
        )

        _log_activity(request.user, 'create', f'ticket_{ticket.id}', f'Создано обращение в поддержку: {subject}', request)
        serializer = SupportTicketSerializer(ticket)
        return Response({
            'success': True,
            'ticket': serializer.data
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class SupportTicketDetailAPIView(APIView):
    """API для работы с конкретным обращением"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        """Получить обращение"""
        if _user_is_manager(request.user):
            ticket = get_object_or_404(SupportTicket, id=ticket_id)
        else:
            ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)

        serializer = SupportTicketSerializer(ticket)
        return Response(serializer.data)

    def put(self, request, ticket_id):
        """Обновить обращение (ответ менеджера)"""
        if not _user_is_manager(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        response_text = request.data.get('response_text', '').strip()
        ticket_status = request.data.get('ticket_status', ticket.ticket_status)

        if response_text:
            ticket.response_text = response_text
        if ticket_status in dict(SupportTicket.TICKET_STATUSES):
            old_status = ticket.ticket_status
            ticket.ticket_status = ticket_status
            if old_status != ticket_status:
                _log_activity(request.user, 'update', f'ticket_{ticket_id}', f'Изменен статус: {old_status} -> {ticket.ticket_status}', request)

        ticket.save()
        _log_activity(request.user, 'update', f'ticket_{ticket_id}', 'Обновлено обращение в поддержку', request)

        serializer = SupportTicketSerializer(ticket)
        return Response({
            'success': True,
            'ticket': serializer.data
        })


# ===== API для каталога и поиска =====
@method_decorator(csrf_exempt, name='dispatch')
class CatalogAPIView(APIView):
    """API для каталога товаров с фильтрацией и поиском"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Получить товары с фильтрацией"""
        q = request.GET.get('q', '').strip()
        category_id = request.GET.get('category')
        brand_id = request.GET.get('brand')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        size_id = request.GET.get('size')
        available_only = request.GET.get('available_only', 'false').lower() == 'true'
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        qs = Product.objects.select_related('category', 'brand').prefetch_related('sizes', 'producttag_set__tag').filter(is_available=True)

        if q:
            qs = qs.filter(Q(product_name__icontains=q) | Q(product_description__icontains=q))
        if category_id:
            qs = qs.filter(category_id=category_id)
        if brand_id:
            qs = qs.filter(brand_id=brand_id)
        if min_price:
            try:
                qs = qs.filter(final_price__gte=Decimal(min_price))
            except (ValueError, InvalidOperation):
                pass
        if max_price:
            try:
                qs = qs.filter(final_price__lte=Decimal(max_price))
            except (ValueError, InvalidOperation):
                pass
        if size_id:
            qs = qs.filter(sizes__id=size_id).distinct()
        if available_only:
            qs = qs.filter(stock_quantity__gt=0)

        qs = qs.order_by('-added_at')
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page)

        serializer = ProductSerializer(page_obj.object_list, many=True)
        return Response({
            'success': True,
            'products': serializer.data,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })


# ===== API для избранного =====
@method_decorator(csrf_exempt, name='dispatch')
class FavoritesAPIView(APIView):
    """API для работы с избранным"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Получить все избранные товары"""
        favorites = Favorite.objects.filter(user=request.user).select_related('product')
        products = [fav.product for fav in favorites]
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Добавить товар в избранное"""
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({
                'success': False,
                'error': 'product_id обязателен'
            }, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id)
        favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)

        if created:
            return Response({
                'success': True,
                'message': 'Товар добавлен в избранное'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': True,
                'message': 'Товар уже в избранном'
            })


@method_decorator(csrf_exempt, name='dispatch')
class FavoriteDetailAPIView(APIView):
    """API для работы с конкретным избранным"""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, product_id):
        """Удалить товар из избранного"""
        favorite = get_object_or_404(Favorite, user=request.user, product_id=product_id)
        favorite.delete()
        return Response({
            'success': True,
            'message': 'Товар удален из избранного'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для отзывов =====
@method_decorator(csrf_exempt, name='dispatch')
class ProductReviewAPIView(APIView):
    """API для работы с отзывами"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id):
        """Получить отзывы на товар"""
        reviews = ProductReview.objects.filter(product_id=product_id).select_related('user').order_by('-created_at')
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request, product_id):
        """Добавить отзыв"""
        product = get_object_or_404(Product, id=product_id)
        rating = int(request.data.get('rating', 0))
        comment = request.data.get('comment', '').strip()

        if not (1 <= rating <= 5):
            return Response({
                'success': False,
                'error': 'Рейтинг должен быть от 1 до 5'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not comment:
            return Response({
                'success': False,
                'error': 'Комментарий обязателен'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, не оставлял ли пользователь уже отзыв
        existing_review = ProductReview.objects.filter(user=request.user, product=product).first()
        if existing_review:
            return Response({
                'success': False,
                'error': 'Вы уже оставили отзыв на этот товар'
            }, status=status.HTTP_400_BAD_REQUEST)

        review = ProductReview.objects.create(
            user=request.user,
            product=product,
            rating=rating,
            comment=comment
        )

        serializer = ProductReviewSerializer(review)
        return Response({
            'success': True,
            'review': serializer.data
        }, status=status.HTTP_201_CREATED)


# ===== API для счета организации (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class OrganizationAccountAPIView(APIView):
    """API для управления счетом организации"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        """Получить информацию о счете организации"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        org_account = OrganizationAccount.get_account()
        transactions = OrganizationTransaction.objects.filter(
            organization_account=org_account
        ).select_related('order', 'created_by').order_by('-created_at')[:50]

        serializer = OrganizationAccountSerializer(org_account)
        transactions_serializer = OrganizationTransactionSerializer(transactions, many=True)

        return Response({
            'success': True,
            'account': serializer.data,
            'transactions': transactions_serializer.data
        })

    def post(self, request):
        """Вывод средств или оплата налога"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        org_account = OrganizationAccount.get_account()

        if action == 'withdraw':
            # Вывод средств на карту админа
            try:
                amount = Decimal(request.data.get('amount', '0'))
            except (ValueError, InvalidOperation):
                return Response({
                    'success': False,
                    'error': 'Неверный формат суммы'
                }, status=status.HTTP_400_BAD_REQUEST)

            card_id = request.data.get('card_id')

            if amount <= 0:
                return Response({
                    'success': False,
                    'error': 'Сумма должна быть больше нуля'
                }, status=status.HTTP_400_BAD_REQUEST)

            org_account.refresh_from_db()

            if not org_account.can_withdraw(amount):
                return Response({
                    'success': False,
                    'error': f'Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not card_id:
                return Response({
                    'success': False,
                    'error': 'Выберите карту для вывода средств'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                card = SavedPaymentMethod.objects.get(id=card_id, user=request.user)
            except SavedPaymentMethod.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Карта не найдена'
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                with transaction.atomic():
                    org_account = OrganizationAccount.objects.select_for_update().get(pk=org_account.pk)
                    
                    if not org_account.can_withdraw(amount):
                        return Response({
                            'success': False,
                            'error': f'Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    balance_before = org_account.balance
                    tax_reserve_before = org_account.tax_reserve

                    org_account.balance -= amount
                    org_account.save()

                    card.balance += amount
                    card.save()

                    OrganizationTransaction.objects.create(
                        organization_account=org_account,
                        transaction_type='withdrawal',
                        amount=amount,
                        description=f'Вывод средств на карту {card.mask_card_number}',
                        created_by=request.user,
                        balance_before=balance_before,
                        balance_after=org_account.balance,
                        tax_reserve_before=tax_reserve_before,
                        tax_reserve_after=org_account.tax_reserve
                    )

                    _log_activity(request.user, 'update', 'org_account', f'Вывод средств {amount} ₽ на карту', request)

                    return Response({
                        'success': True,
                        'message': f'Средства в размере {amount} ₽ выведены на карту'
                    })
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Ошибка при выводе средств: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif action == 'pay_tax':
            # Оплата налога
            try:
                amount = Decimal(request.data.get('amount', '0'))
            except (ValueError, InvalidOperation):
                return Response({
                    'success': False,
                    'error': 'Неверный формат суммы'
                }, status=status.HTTP_400_BAD_REQUEST)

            if amount <= 0:
                return Response({
                    'success': False,
                    'error': 'Сумма должна быть больше нуля'
                }, status=status.HTTP_400_BAD_REQUEST)

            org_account.refresh_from_db()

            if not org_account.can_pay_tax(amount):
                if org_account.tax_reserve < amount:
                    error_msg = f'Недостаточно средств в резерве на налоги. Доступно: {org_account.tax_reserve} ₽, запрошено: {amount} ₽'
                elif org_account.balance < amount:
                    error_msg = f'Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽'
                else:
                    error_msg = f'Недостаточно средств для оплаты налога'
                return Response({
                    'success': False,
                    'error': error_msg
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                with transaction.atomic():
                    org_account = OrganizationAccount.objects.select_for_update().get(pk=org_account.pk)
                    
                    if not org_account.can_pay_tax(amount):
                        if org_account.tax_reserve < amount:
                            error_msg = f'Недостаточно средств в резерве на налоги. Доступно: {org_account.tax_reserve} ₽, запрошено: {amount} ₽'
                        elif org_account.balance < amount:
                            error_msg = f'Недостаточно средств на счете организации. Доступно: {org_account.balance} ₽, запрошено: {amount} ₽'
                        else:
                            error_msg = f'Недостаточно средств для оплаты налога'
                        return Response({
                            'success': False,
                            'error': error_msg
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
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

                    return Response({
                        'success': True,
                        'message': f'Налог в размере {amount} ₽ оплачен'
                    })
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Ошибка при оплате налога: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': False,
            'error': 'Неверное действие'
        }, status=status.HTTP_400_BAD_REQUEST)


# ===== API для управления промокодами (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class PromotionManagementAPIView(APIView):
    """API для управления промокодами (только для админов)"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        """Получить список промокодов с фильтрацией"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        q = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))

        qs = Promotion.objects.all().order_by('-start_date', 'promo_code')

        if q:
            qs = qs.filter(Q(promo_code__icontains=q) | Q(promo_description__icontains=q))

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(page)

        promotions_data = []
        for promo in page_obj.object_list:
            promotions_data.append({
                'id': promo.id,
                'promo_code': promo.promo_code,
                'promo_description': promo.promo_description,
                'discount': float(promo.discount),
                'start_date': promo.start_date.isoformat() if promo.start_date else None,
                'end_date': promo.end_date.isoformat() if promo.end_date else None,
                'is_active': promo.is_active
            })

        return Response({
            'success': True,
            'promotions': promotions_data,
            'pagination': {
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })

    def post(self, request):
        """Создать новый промокод"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        promo_code = request.data.get('promo_code', '').strip().upper()
        promo_description = request.data.get('promo_description', '').strip()
        discount_str = request.data.get('discount', '0')
        start_date_str = request.data.get('start_date', '').strip()
        end_date_str = request.data.get('end_date', '').strip()
        is_active = request.data.get('is_active', True)

        if not promo_code:
            return Response({
                'success': False,
                'error': 'Код промокода обязателен'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            discount = Decimal(discount_str) if discount_str else Decimal('0')
        except (ValueError, InvalidOperation):
            discount = Decimal('0')

        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_date_str:
            try:
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

        return Response({
            'success': True,
            'promotion_id': promotion.id,
            'message': 'Промокод создан'
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class PromotionManagementDetailAPIView(APIView):
    """API для работы с конкретным промокодом"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, promo_id):
        """Получить промокод"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        promotion = get_object_or_404(Promotion, id=promo_id)
        serializer = PromotionSerializer(promotion)
        return Response({
            'success': True,
            'promotion': serializer.data
        })

    def put(self, request, promo_id):
        """Обновить промокод"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        promotion = get_object_or_404(Promotion, id=promo_id)

        promo_code = request.data.get('promo_code', '').strip().upper()
        promo_description = request.data.get('promo_description', '').strip()
        discount_str = request.data.get('discount', '0')
        start_date_str = request.data.get('start_date', '').strip()
        end_date_str = request.data.get('end_date', '').strip()
        is_active = request.data.get('is_active', True)

        if not promo_code:
            return Response({
                'success': False,
                'error': 'Код промокода обязателен'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            discount = Decimal(discount_str) if discount_str else Decimal('0')
        except (ValueError, InvalidOperation):
            discount = Decimal('0')

        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        promotion.promo_code = promo_code
        promotion.promo_description = promo_description
        promotion.discount = discount
        promotion.start_date = start_date
        promotion.end_date = end_date
        promotion.is_active = is_active
        promotion.save()

        _log_activity(request.user, 'update', f'promotion_{promo_id}', f'Обновлен промокод: {promo_code}', request)

        return Response({
            'success': True,
            'message': 'Промокод обновлен'
        })

    def delete(self, request, promo_id):
        """Удалить промокод"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        promotion = get_object_or_404(Promotion, id=promo_id)
        promo_code = promotion.promo_code
        promotion.delete()

        _log_activity(request.user, 'delete', f'promotion_{promo_id}', f'Удален промокод: {promo_code}', request)

        return Response({
            'success': True,
            'message': f'Промокод {promo_code} удален'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для управления поставщиками (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class SupplierManagementAPIView(APIView):
    """API для управления поставщиками (только для админов)"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        """Получить список поставщиков с фильтрацией"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        q = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))

        qs = Supplier.objects.all().order_by('supplier_name')

        if q:
            qs = qs.filter(
                Q(supplier_name__icontains=q) |
                Q(contact_person__icontains=q) |
                Q(contact_email__icontains=q) |
                Q(contact_phone__icontains=q)
            )

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(page)

        suppliers_data = []
        for supplier in page_obj.object_list:
            suppliers_data.append({
                'id': supplier.id,
                'supplier_name': supplier.supplier_name,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'contact_email': supplier.contact_email,
                'supply_country': supplier.supply_country,
                'delivery_cost': float(supplier.delivery_cost) if supplier.delivery_cost else None,
                'supplier_type': supplier.supplier_type
            })

        return Response({
            'success': True,
            'suppliers': suppliers_data,
            'pagination': {
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })

    def post(self, request):
        """Создать нового поставщика"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        supplier_name = request.data.get('supplier_name', '').strip()
        contact_person = request.data.get('contact_person', '').strip()
        contact_phone = request.data.get('contact_phone', '').strip()
        contact_email = request.data.get('contact_email', '').strip()
        supply_country = request.data.get('supply_country', '').strip()
        delivery_cost_str = request.data.get('delivery_cost', '').strip()
        supplier_type = request.data.get('supplier_type', '').strip()

        if not supplier_name:
            return Response({
                'success': False,
                'error': 'Название поставщика обязательно'
            }, status=status.HTTP_400_BAD_REQUEST)

        delivery_cost = None
        if delivery_cost_str:
            try:
                delivery_cost = Decimal(delivery_cost_str)
            except (ValueError, InvalidOperation):
                pass

        supplier = Supplier.objects.create(
            supplier_name=supplier_name,
            contact_person=contact_person or None,
            contact_phone=contact_phone or None,
            contact_email=contact_email or None,
            supply_country=supply_country or None,
            delivery_cost=delivery_cost,
            supplier_type=supplier_type or None
        )

        _log_activity(request.user, 'create', f'supplier_{supplier.id}', f'Создан поставщик: {supplier_name}', request)

        return Response({
            'success': True,
            'supplier_id': supplier.id,
            'message': 'Поставщик создан'
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class SupplierManagementDetailAPIView(APIView):
    """API для работы с конкретным поставщиком"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, supplier_id):
        """Получить поставщика"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        supplier = get_object_or_404(Supplier, id=supplier_id)
        serializer = SupplierSerializer(supplier)
        return Response({
            'success': True,
            'supplier': serializer.data
        })

    def put(self, request, supplier_id):
        """Обновить поставщика"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        supplier = get_object_or_404(Supplier, id=supplier_id)

        supplier_name = request.data.get('supplier_name', '').strip()
        contact_person = request.data.get('contact_person', '').strip()
        contact_phone = request.data.get('contact_phone', '').strip()
        contact_email = request.data.get('contact_email', '').strip()
        supply_country = request.data.get('supply_country', '').strip()
        delivery_cost_str = request.data.get('delivery_cost', '').strip()
        supplier_type = request.data.get('supplier_type', '').strip()

        if not supplier_name:
            return Response({
                'success': False,
                'error': 'Название поставщика обязательно'
            }, status=status.HTTP_400_BAD_REQUEST)

        delivery_cost = None
        if delivery_cost_str:
            try:
                delivery_cost = Decimal(delivery_cost_str)
            except (ValueError, InvalidOperation):
                pass

        supplier.supplier_name = supplier_name
        supplier.contact_person = contact_person or None
        supplier.contact_phone = contact_phone or None
        supplier.contact_email = contact_email or None
        supplier.supply_country = supply_country or None
        supplier.delivery_cost = delivery_cost
        supplier.supplier_type = supplier_type or None
        supplier.save()

        _log_activity(request.user, 'update', f'supplier_{supplier_id}', f'Обновлен поставщик: {supplier_name}', request)

        return Response({
            'success': True,
            'message': 'Поставщик обновлен'
        })

    def delete(self, request, supplier_id):
        """Удалить поставщика"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        supplier = get_object_or_404(Supplier, id=supplier_id)
        supplier_name = supplier.supplier_name
        supplier.delete()

        _log_activity(request.user, 'delete', f'supplier_{supplier_id}', f'Удален поставщик: {supplier_name}', request)

        return Response({
            'success': True,
            'message': f'Поставщик {supplier_name} удален'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для управления ролями (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class RoleManagementAPIView(APIView):
    """API для управления ролями (только для админов)"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        """Получить список ролей"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        roles = Role.objects.all().order_by('role_name')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'roles': serializer.data
        })

    def post(self, request):
        """Создать новую роль"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        role_name = request.data.get('role_name', '').strip()

        if not role_name:
            return Response({
                'success': False,
                'error': 'Название роли обязательно'
            }, status=status.HTTP_400_BAD_REQUEST)

        if Role.objects.filter(role_name=role_name).exists():
            return Response({
                'success': False,
                'error': 'Роль с таким названием уже существует'
            }, status=status.HTTP_400_BAD_REQUEST)

        role = Role.objects.create(role_name=role_name)
        _log_activity(request.user, 'create', f'role_{role.id}', f'Создана роль: {role_name}', request)

        return Response({
            'success': True,
            'role_id': role.id,
            'message': 'Роль создана'
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class RoleManagementDetailAPIView(APIView):
    """API для работы с конкретной ролью"""
    permission_classes = [IsAdminOrReadOnly]

    def delete(self, request, role_id):
        """Удалить роль"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        role = get_object_or_404(Role, id=role_id)
        role_name = role.role_name
        role.delete()

        _log_activity(request.user, 'delete', f'role_{role_id}', f'Удалена роль: {role_name}', request)

        return Response({
            'success': True,
            'message': f'Роль {role_name} удалена'
        }, status=status.HTTP_204_NO_CONTENT)


# ===== API для управления бэкапами (Только Админ) =====
@method_decorator(csrf_exempt, name='dispatch')
class BackupManagementAPIView(APIView):
    """API для управления бэкапами (только для админов)"""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        """Получить список бэкапов"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        from .models import DatabaseBackup
        page = int(request.GET.get('page', 1))
        qs = DatabaseBackup.objects.select_related('created_by').all().order_by('-created_at')

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(page)

        backups_data = []
        for backup in page_obj.object_list:
            backups_data.append({
                'id': backup.id,
                'backup_name': backup.backup_name,
                'created_at': backup.created_at.isoformat(),
                'created_by': backup.created_by.username if backup.created_by else 'Система',
                'file_size_mb': backup.get_file_size_mb(),
                'schedule': backup.schedule,
                'schedule_display': backup.get_schedule_display(),
                'is_automatic': backup.is_automatic,
                'notes': backup.notes
            })

        return Response({
            'success': True,
            'backups': backups_data,
            'pagination': {
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })

    def post(self, request):
        """Создать бэкап"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            from .models import DatabaseBackup
            import shutil
            import os
            from django.conf import settings

            backup_name = request.data.get('backup_name', '').strip()
            schedule = request.data.get('schedule', 'now')
            notes = request.data.get('notes', '').strip() or None

            # Получаем путь к базе данных
            db_path = settings.DATABASES['default']['NAME']
            if not os.path.exists(db_path):
                return Response({
                    'success': False,
                    'error': 'База данных не найдена'
                }, status=status.HTTP_404_NOT_FOUND)

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
            if not backup_name:
                backup_name = f'Бэкап от {datetime.now().strftime("%d.%m.%Y %H:%M")}'

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

            return Response({
                'success': True,
                'backup_id': backup.id,
                'message': f'Бэкап "{backup_name}" успешно создан'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при создании бэкапа: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class BackupManagementDetailAPIView(APIView):
    """API для работы с конкретным бэкапом"""
    permission_classes = [IsAdminOrReadOnly]

    def delete(self, request, backup_id):
        """Удалить бэкап"""
        if not _user_is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Доступ запрещен'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            from .models import DatabaseBackup
            import os
            from django.conf import settings

            backup = get_object_or_404(DatabaseBackup, id=backup_id)
            backup_name = backup.backup_name

            # Удаляем файл, если он существует
            if backup.backup_file:
                file_path = os.path.join(settings.MEDIA_ROOT, backup.backup_file.name)
                if os.path.exists(file_path):
                    os.remove(file_path)

            backup.delete()

            _log_activity(request.user, 'delete', f'backup_{backup_id}', f'Удален бэкап: {backup_name}', request)

            return Response({
                'success': True,
                'message': f'Бэкап "{backup_name}" удален'
            }, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при удалении бэкапа: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
