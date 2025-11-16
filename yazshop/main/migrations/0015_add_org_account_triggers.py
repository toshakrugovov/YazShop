# Generated manually

from django.db import migrations


def create_triggers(apps, schema_editor):
    """Создает триггеры для проверки баланса при обновлении счета организации"""
    db_alias = schema_editor.connection.alias
    
    # Триггер для проверки баланса при выводе средств
    # Проверяет, что баланс не станет отрицательным
    schema_editor.execute("""
        CREATE TRIGGER IF NOT EXISTS check_org_account_balance_before_update
        BEFORE UPDATE ON main_organizationaccount
        FOR EACH ROW
        WHEN NEW.balance < 0
        BEGIN
            SELECT RAISE(ABORT, 'Недостаточно средств на счете организации. Попытка вывести больше, чем доступно.');
        END;
    """)
    
    # Триггер для проверки резерва на налоги
    schema_editor.execute("""
        CREATE TRIGGER IF NOT EXISTS check_org_account_tax_reserve_before_update
        BEFORE UPDATE ON main_organizationaccount
        FOR EACH ROW
        WHEN NEW.tax_reserve < 0
        BEGIN
            SELECT RAISE(ABORT, 'Недостаточно средств в резерве на налоги. Попытка оплатить больше, чем зарезервировано.');
        END;
    """)
    
    # Триггер для проверки при оплате налога (должен быть баланс >= суммы налога)
    schema_editor.execute("""
        CREATE TRIGGER IF NOT EXISTS check_org_account_tax_payment
        BEFORE UPDATE ON main_organizationaccount
        FOR EACH ROW
        WHEN NEW.balance < OLD.balance AND NEW.tax_reserve < OLD.tax_reserve
            AND (NEW.balance < (OLD.balance - (OLD.tax_reserve - NEW.tax_reserve)))
        BEGIN
            SELECT RAISE(ABORT, 'Недостаточно средств на счете для оплаты налога.');
        END;
    """)


def drop_triggers(apps, schema_editor):
    """Удаляет триггеры"""
    schema_editor.execute("DROP TRIGGER IF EXISTS check_org_account_balance_before_update;")
    schema_editor.execute("DROP TRIGGER IF EXISTS check_org_account_tax_reserve_before_update;")
    schema_editor.execute("DROP TRIGGER IF EXISTS check_org_account_tax_payment;")


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_add_org_account_constraints'),
    ]

    operations = [
        migrations.RunPython(create_triggers, drop_triggers),
    ]

