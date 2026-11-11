-- Repairs a database where CMS migration 0003 was recorded under a name that is not in the repository
-- ("0003_pages_nav_seo", applied 5 Nov 2026 from a file that was never committed). That stray migration created
-- cms_seorecord, cms_navigationitem, cms_page and cms_redirect, so the real
-- "0003_pages_navigation_seo_redirects" fails with: relation "cms_seorecord" already exists.
--
-- What it does, in ONE transaction (any check that fails rolls everything back and changes nothing):
--   1. Lists migration records that don't exist in the repository (for information).
--   2. Checks the four tables have exactly the columns, types and nullability the real 0003 creates.
--   3. Adds what the stray migration left out (draft columns, constraints, indexes), only if missing.
--   4. Renames the stray record to the real migration name, so Django sees 0003 as applied.
-- It never drops or deletes data. Take a backup first (see docs/operations/backup-restore.md).
--
-- Run (PowerShell, from the repository folder):
--   Get-Content scripts/ops/repair_cms_0003.sql -Raw | docker compose -f infra/compose.yaml exec -T postgres psql -v ON_ERROR_STOP=1 -U aurevon -d aurevon

\set ON_ERROR_STOP on
BEGIN;

-- 1. Records the repository doesn't know (informational).
CREATE TEMP TABLE expected_migration (app text, name text) ON COMMIT DROP;
INSERT INTO expected_migration VALUES
    ('accounts', '0001_initial'),
    ('accounts', '0002_account_type_is_permanent'),
    ('audit', '0001_initial'),
    ('audit', '0002_append_only'),
    ('auth', '0001_initial'),
    ('auth', '0002_alter_permission_name_max_length'),
    ('auth', '0003_alter_user_email_max_length'),
    ('auth', '0004_alter_user_username_opts'),
    ('auth', '0005_alter_user_last_login_null'),
    ('auth', '0006_require_contenttypes_0002'),
    ('auth', '0007_alter_validators_add_error_messages'),
    ('auth', '0008_alter_user_username_max_length'),
    ('auth', '0009_alter_user_last_name_max_length'),
    ('auth', '0010_alter_group_name_max_length'),
    ('auth', '0011_update_proxy_permissions'),
    ('auth', '0012_alter_user_first_name_max_length'),
    ('cart', '0001_initial'),
    ('catalog', '0001_initial'),
    ('catalog', '0002_p12_expand'),
    ('catalog', '0003_p12_move_data'),
    ('catalog', '0004_p12_contract'),
    ('catalog', '0005_product_image_storage'),
    ('catalog', '0006_threed_assets'),
    ('cms', '0001_initial'),
    ('cms', '0002_banner_homepagesection'),
    ('cms', '0003_pages_navigation_seo_redirects'),
    ('contenttypes', '0001_initial'),
    ('contenttypes', '0002_remove_content_type_name'),
    ('customers', '0001_initial'),
    ('inventory', '0001_initial'),
    ('inventory', '0002_locations_and_items'),
    ('inventory', '0003_stockreservation_and_more'),
    ('inventory', '0004_suppliers_purchase_orders_reorder_levels'),
    ('localization', '0001_initial'),
    ('notifications', '0001_initial'),
    ('notifications', '0002_staffalert'),
    ('notifications', '0003_consent_purposes_cart_reminders_sms'),
    ('orders', '0001_initial'),
    ('orders', '0002_exchange_payment_method'),
    ('payments', '0001_initial'),
    ('promotions', '0001_initial'),
    ('returns', '0001_initial'),
    ('sandbox', '0001_initial'),
    ('shipping', '0001_initial'),
    ('support', '0001_initial');
SELECT 'not in repository' AS note, m.app, m.name, m.applied
FROM django_migrations m LEFT JOIN expected_migration e ON e.app = m.app AND e.name = m.name
WHERE e.app IS NULL ORDER BY m.id;

-- 2 and 3. Check, then complete the schema.
DO $repair$
DECLARE
  problems text := '';
  want record;
  got record;
BEGIN
  IF EXISTS (SELECT 1 FROM django_migrations WHERE app = 'cms' AND name = '0003_pages_navigation_seo_redirects') THEN
    RAISE NOTICE 'cms 0003_pages_navigation_seo_redirects is already recorded: nothing to repair.';
    RETURN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'cms' AND name = '0003_pages_nav_seo') THEN
    RAISE EXCEPTION 'Expected a cms record named 0003_pages_nav_seo; not found. Nothing changed.';
  END IF;

  -- Every column the real 0003 creates: table, column, type, nullable.
  FOR want IN SELECT * FROM (VALUES
    ('cms_seorecord','key','character varying(100)','NO'),
    ('cms_seorecord','content','jsonb','NO'),
    ('cms_seorecord','noindex','boolean','NO'),
    ('cms_seorecord','updated_at','timestamp with time zone','NO'),
    ('cms_navigationitem','id','uuid','NO'),
    ('cms_navigationitem','menu','character varying(20)','NO'),
    ('cms_navigationitem','label','jsonb','NO'),
    ('cms_navigationitem','href','character varying(200)','NO'),
    ('cms_navigationitem','position','integer','NO'),
    ('cms_page','id','uuid','NO'),
    ('cms_page','slug','character varying(80)','NO'),
    ('cms_page','kind','character varying(10)','NO'),
    ('cms_page','is_published','boolean','NO'),
    ('cms_page','published_at','timestamp with time zone','YES'),
    ('cms_page','content','jsonb','NO'),
    ('cms_page','draft','jsonb','YES'),
    ('cms_page','created_at','timestamp with time zone','NO'),
    ('cms_page','updated_at','timestamp with time zone','NO'),
    ('cms_redirect','id','uuid','NO'),
    ('cms_redirect','from_path','character varying(200)','NO'),
    ('cms_redirect','to_path','character varying(200)','NO'),
    ('cms_redirect','is_permanent','boolean','NO'),
    ('cms_redirect','source','character varying(20)','NO'),
    ('cms_redirect','created_at','timestamp with time zone','NO')
  ) AS t(tbl, col, typ, nullable)
  LOOP
    SELECT format_type(a.atttypid, a.atttypmod) AS typ, CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS nullable
      INTO got
      FROM pg_attribute a
     WHERE a.attrelid = to_regclass('public.' || want.tbl) AND a.attname = want.col AND NOT a.attisdropped;
    IF NOT FOUND THEN
      problems := problems || format(E'\n  %s.%s is missing', want.tbl, want.col);
    ELSIF got.typ <> want.typ OR got.nullable <> want.nullable THEN
      problems := problems || format(E'\n  %s.%s is %s (nullable %s), expected %s (nullable %s)',
        want.tbl, want.col, got.typ, got.nullable, want.typ, want.nullable);
    END IF;
  END LOOP;
  IF problems <> '' THEN
    RAISE EXCEPTION 'The existing CMS tables differ from migration 0003; nothing changed:%', problems;
  END IF;

  -- What the stray migration left out (each only if missing).
  ALTER TABLE cms_banner ADD COLUMN IF NOT EXISTS draft jsonb NULL;
  ALTER TABLE cms_homepagesection ADD COLUMN IF NOT EXISTS draft jsonb NULL;
  CREATE INDEX IF NOT EXISTS cms_seorecord_key_b9c613e6_like ON cms_seorecord (key varchar_pattern_ops);
  CREATE INDEX IF NOT EXISTS cms_page_slug_79813086_like ON cms_page (slug varchar_pattern_ops);
  CREATE INDEX IF NOT EXISTS cms_redirect_from_path_36e4225a_like ON cms_redirect (from_path varchar_pattern_ops);

  -- Primary keys and unique constraints the real 0003 declares.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_seorecord'::regclass AND contype = 'p') THEN
    ALTER TABLE cms_seorecord ADD PRIMARY KEY (key);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_navigationitem'::regclass AND contype = 'p') THEN
    ALTER TABLE cms_navigationitem ADD PRIMARY KEY (id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_page'::regclass AND contype = 'p') THEN
    ALTER TABLE cms_page ADD PRIMARY KEY (id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_redirect'::regclass AND contype = 'p') THEN
    ALTER TABLE cms_redirect ADD PRIMARY KEY (id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_page'::regclass AND contype = 'u'
                 AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'cms_page'::regclass AND attname = 'slug')]) THEN
    ALTER TABLE cms_page ADD CONSTRAINT cms_page_slug_key UNIQUE (slug);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_redirect'::regclass AND contype = 'u'
                 AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'cms_redirect'::regclass AND attname = 'from_path')]) THEN
    ALTER TABLE cms_redirect ADD CONSTRAINT cms_redirect_from_path_key UNIQUE (from_path);
  END IF;

  -- Named check constraints (added only if missing; existing rows must satisfy them or the whole repair rolls back).
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'navigation_menu_valid') THEN
    ALTER TABLE cms_navigationitem ADD CONSTRAINT navigation_menu_valid CHECK (menu IN ('header', 'footer_shop', 'footer_help'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'cms_navigationitem'::regclass AND contype = 'c'
                 AND pg_get_constraintdef(oid) LIKE '%position%>= 0%') THEN
    ALTER TABLE cms_navigationitem ADD CONSTRAINT cms_navigationitem_position_check CHECK (position >= 0);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'page_kind_valid') THEN
    ALTER TABLE cms_page ADD CONSTRAINT page_kind_valid CHECK (kind IN ('content', 'policy'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'page_published_has_date') THEN
    ALTER TABLE cms_page ADD CONSTRAINT page_published_has_date CHECK (NOT is_published OR published_at IS NOT NULL);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'redirect_source_valid') THEN
    ALTER TABLE cms_redirect ADD CONSTRAINT redirect_source_valid CHECK (source IN ('manual', 'slug_change'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'redirect_not_to_itself') THEN
    ALTER TABLE cms_redirect ADD CONSTRAINT redirect_not_to_itself CHECK (NOT (from_path = to_path));
  END IF;

  -- 4. The schema now matches 0003: record it under its real name (the stray row keeps its id and date).
  UPDATE django_migrations SET name = '0003_pages_navigation_seo_redirects'
   WHERE app = 'cms' AND name = '0003_pages_nav_seo';
  RAISE NOTICE 'Repaired: cms 0003 recorded as 0003_pages_navigation_seo_redirects; schema completed.';
END
$repair$;

COMMIT;
