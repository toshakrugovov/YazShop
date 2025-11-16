"""
Вспомогательные функции для проверки прав доступа и логирования
"""
from django.contrib.auth.models import User
from .models import ActivityLog


def _user_is_admin(user) -> bool:
    """Проверка, является ли пользователь администратором"""
    try:
        if getattr(user, 'is_superuser', False):
            return True
        prof = getattr(user, 'profile', None)
        if not prof or not prof.role:
            return False
        return str(prof.role.role_name or '').strip().lower() in ('admin', 'админ', 'administrator')
    except Exception:
        return False


def _user_is_manager(user) -> bool:
    """Проверка, является ли пользователь менеджером"""
    try:
        if getattr(user, 'is_superuser', False):
            return True
        if _user_is_admin(user):
            return True
        prof = getattr(user, 'profile', None)
        if not prof or not prof.role:
            return False
        role_name = str(prof.role.role_name or '').strip().lower()
        return role_name in ('manager', 'менеджер', 'manager')
    except Exception:
        return False


def _log_activity(user, action_type, target_object, description='', request=None):
    """Функция для логирования действий пользователей"""
    try:
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
        
        ActivityLog.objects.create(
            user=user,
            action_type=action_type,
            target_object=target_object,
            action_description=description,
            ip_address=ip_address
        )
    except Exception:
        pass  # Не прерываем выполнение при ошибке логирования

