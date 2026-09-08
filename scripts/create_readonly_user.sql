-- ============================================================
-- Kervansaray - Salt-Okunur (Read-Only) Veritabanı Kullanıcısı
-- ============================================================
-- Bu script, public demo veya yalnızca sorgulama yapan servisler için
-- DROP, DELETE, UPDATE, INSERT yetkisi OLMAYAN bir kullanıcı yaratır.
--
-- Çalıştırma:
--   docker exec -i kervansaray_db psql -U kervansaray -d kervansaray < scripts/create_readonly_user.sql
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kervansaray_readonly') THEN
        CREATE ROLE kervansaray_readonly WITH LOGIN PASSWORD 'kervansaray_readonly_pass';
    END IF;
END
$$;

-- 1. Veritabanı ve public şemasına bağlanma yetkisi
GRANT CONNECT ON DATABASE kervansaray TO kervansaray_readonly;
GRANT USAGE ON SCHEMA public TO kervansaray_readonly;

-- 2. Mevcut tüm tablolara ve v_events view'una yalnızca SELECT yetkisi ver
GRANT SELECT ON ALL TABLES IN SCHEMA public TO kervansaray_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO kervansaray_readonly;

-- 3. Gelecekte eklenecek tablolara da otomatik SELECT yetkisi ata
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO kervansaray_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO kervansaray_readonly;

-- 4. Kesin güvenlik: Yazma ve yapı değiştirme haklarını açıkça iptal et (fail-closed)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM kervansaray_readonly;
