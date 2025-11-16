from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib import messages

class AdminAccessMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Исключаем статические файлы, медиа и API из проверки
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.path.startswith('/api/') or
            request.path.startswith('/swagger/') or
            request.path.startswith('/redoc/')):
            return self.get_response(request)
        
        # Проверяем доступ к админке только для HTML страниц
        if request.path.startswith('/admin/'):
            # Разрешаем доступ к статическим файлам админки и JavaScript интернационализации
            if (request.path.startswith('/admin/static/') or 
                request.path.startswith('/admin/jsi18n/') or
                request.path.endswith('.css') or
                request.path.endswith('.js') or
                request.path.endswith('.png') or
                request.path.endswith('.jpg') or
                request.path.endswith('.gif') or
                request.path.endswith('.svg') or
                request.path.endswith('.ico')):
                return self.get_response(request)
            # Разрешаем доступ, только если сессия содержит admin_access_granted
            if not request.session.get('admin_access_granted', False):
                return redirect(reverse('custom_admin_login'))
        return self.get_response(request)


class BlockedUserMiddleware:
    """Middleware для проверки статуса пользователя и блокировки доступа заблокированным пользователям"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Исключаем статические файлы, медиа, API и страницы входа/регистрации
        excluded_paths = [
            '/static/', '/media/', '/api/', '/swagger/', '/redoc/',
            '/login/', '/register/', '/logout/'
        ]
        
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)
        
        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated:
            # Проверка is_active (стандартное поле Django)
            if not request.user.is_active:
                logout(request)
                messages.error(request, 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka')
                return redirect('login')
            
            # Проверка статуса в профиле
            try:
                profile = request.user.profile
                if profile.user_status == 'blocked':
                    logout(request)
                    messages.error(request, 'Ваш аккаунт заблокирован. Обратитесь в поддержку: https://t.me/toshaplenka')
                    return redirect('login')
            except Exception:
                # Если профиля нет, пропускаем проверку
                pass
        
        return self.get_response(request)
