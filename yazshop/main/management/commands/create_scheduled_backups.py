"""
Management command для создания автоматических бэкапов по расписанию
Запускать через cron или планировщик задач Windows
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from main.models import DatabaseBackup
from django.contrib.auth.models import User
import shutil
import os
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Создает автоматические бэкапы базы данных по расписанию'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schedule',
            type=str,
            choices=['weekly', 'monthly', 'yearly'],
            help='Тип расписания для создания бэкапа',
        )

    def handle(self, *args, **options):
        schedule = options.get('schedule')
        
        if not schedule:
            self.stdout.write(self.style.ERROR('Не указан тип расписания'))
            return
        
        # Получаем путь к базе данных
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f'База данных не найдена: {db_path}'))
            return
        
        # Проверяем, нужно ли создавать бэкап
        now = timezone.now()
        last_backup = DatabaseBackup.objects.filter(
            schedule=schedule,
            is_automatic=True
        ).order_by('-created_at').first()
        
        should_create = False
        if not last_backup:
            should_create = True
        else:
            if schedule == 'weekly':
                # Проверяем, прошла ли неделя
                if now - last_backup.created_at >= timedelta(days=7):
                    should_create = True
            elif schedule == 'monthly':
                # Проверяем, прошел ли месяц
                if now - last_backup.created_at >= timedelta(days=30):
                    should_create = True
            elif schedule == 'yearly':
                # Проверяем, прошел ли год
                if now - last_backup.created_at >= timedelta(days=365):
                    should_create = True
        
        if not should_create:
            self.stdout.write(self.style.SUCCESS(f'Бэкап по расписанию {schedule} не требуется'))
            return
        
        try:
            # Создаем директорию для бэкапов, если её нет
            backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Генерируем имя файла бэкапа
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'db_backup_{schedule}_{timestamp}.sqlite3'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Копируем файл базы данных
            shutil.copy2(db_path, backup_path)
            
            # Получаем размер файла
            file_size = os.path.getsize(backup_path)
            
            # Получаем первого суперпользователя или создаем системного
            admin_user = User.objects.filter(is_superuser=True).first()
            
            # Создаем запись в базе данных
            schedule_names = {
                'weekly': 'Еженедельный',
                'monthly': 'Ежемесячный',
                'yearly': 'Ежегодный'
            }
            backup_name = f'{schedule_names[schedule]} бэкап от {datetime.now().strftime("%d.%m.%Y %H:%M")}'
            
            backup = DatabaseBackup.objects.create(
                backup_name=backup_name,
                created_by=admin_user,
                file_size=file_size,
                schedule=schedule,
                notes=f'Автоматический бэкап по расписанию: {schedule}',
                is_automatic=True
            )
            
            # Сохраняем путь к файлу
            backup.backup_file.name = f'backups/{backup_filename}'
            backup.save()
            
            self.stdout.write(self.style.SUCCESS(f'Бэкап "{backup_name}" успешно создан'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при создании бэкапа: {str(e)}'))

