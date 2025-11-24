-- Убеждаемся, что база использует UTF8
UPDATE pg_database SET datcollate='en_US.UTF-8', datctype='en_US.UTF-8' WHERE datname='ticketbot_utf8';

-- Создаем расширения если нужны
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Настраиваем параметры для лучшей производительности
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Перезагружаем конфигурацию
SELECT pg_reload_conf();