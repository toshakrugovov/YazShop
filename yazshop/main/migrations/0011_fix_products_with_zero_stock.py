from django.db import migrations

def fix_products_with_zero_stock(apps, schema_editor):
    """Отключает товары с нулевым остатком"""
    Product = apps.get_model('main', 'Product')
    # Находим все товары с остатком 0 или меньше, но с is_available=True
    products_to_disable = Product.objects.filter(stock_quantity__lte=0, is_available=True)
    count = products_to_disable.update(is_available=False)
    print(f"Отключено товаров с нулевым остатком: {count}")

def reverse_fix(apps, schema_editor):
    """Обратная операция - не требуется"""
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_fix_negative_card_balances'),
    ]

    operations = [
        migrations.RunPython(fix_products_with_zero_stock, reverse_fix),
    ]

