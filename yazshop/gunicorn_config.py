# Gunicorn конфигурация для продакшена

bind = "unix:/home/yazshop/yazshop/yazshop/yazshop.sock"
workers = 3
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Логирование
accesslog = "/home/yazshop/yazshop/logs/access.log"
errorlog = "/home/yazshop/yazshop/logs/error.log"
loglevel = "info"

# Безопасность
user = "yazshop"
group = "www-data"
umask = 0o007

# Перезапуск при изменении кода (только для разработки)
reload = False

