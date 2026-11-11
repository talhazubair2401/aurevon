-- Repairs a database where CMS migration 0003 was applied from a file that was never committed
-- ("0003_pages_nav_seo", 5 Nov 2026). That stray migration created cms_seorecord, cms_navigationitem, cms_page
-- and cms_redirect with a DIFFERENT design from the repository's 0003_pages_navigation_seo_redirects, so the
-- real migration fails with: relation "cms_seorecord" already exists.
--
-- Fix, in ONE transaction (any failed check rolls everything back and changes nothing):
--   1. Confirms the four tables have the stray design (not the real one) and reports their row counts.
--   2. Moves them, with their data, indexes and constraints, into a separate schema, cms_stray_0003.
--      Nothing is dropped or deleted; they stay readable there (select * from cms_stray_0003.cms_page).
--   3. Leaves the stray record in django_migrations untouched (Django ignores records with no file).
-- Afterwards `python manage.py migrate` (the Compose "migrate" service) creates the real tables.
-- Take a backup first (docs/operations/backup-restore.md).
--
-- Run (PowerShell, from the repository folder):
--   docker compose -f infra/compose.yaml cp scripts/ops/repair_cms_0003.sql postgres:/tmp/repair_cms_0003.sql
--   docker compose -f infra/compose.yaml exec postgres psql -v ON_ERROR_STOP=1 -U aurevon -d aurevon -f /tmp/repair_cms_0003.sql

\set ON_ERROR_STOP on
BEGIN;

SELECT 'cms_seorecord' AS stray_table, count(*) AS rows FROM cms_seorecord
UNION ALL SELECT 'cms_navigationitem', count(*) FROM cms_navigationitem
UNION ALL SELECT 'cms_page', count(*) FROM cms_page
UNION ALL SELECT 'cms_redirect', count(*) FROM cms_redirect;

DO $repair$
DECLARE
  col text;
BEGIN
  IF EXISTS (SELECT 1 FROM django_migrations WHERE app = 'cms' AND name = '0003_pages_navigation_seo_redirects') THEN
    RAISE EXCEPTION 'The real cms 0003 is already recorded: nothing to repair. Nothing changed.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'cms' AND name = '0003_pages_nav_seo') THEN
    RAISE EXCEPTION 'No stray cms record 0003_pages_nav_seo found. Nothing changed.';
  END IF;
  IF to_regnamespace('cms_stray_0003') IS NOT NULL THEN
    RAISE EXCEPTION 'Schema cms_stray_0003 already exists: the repair has run before. Nothing changed.';
  END IF;

  -- The stray design, as found on the affected database: every one of these columns must be present.
  FOREACH col IN ARRAY ARRAY[
    'cms_seorecord.path', 'cms_seorecord.locale', 'cms_seorecord.title', 'cms_seorecord.canonical_path',
    'cms_navigationitem.location', 'cms_navigationitem.group_key', 'cms_navigationitem.is_enabled',
    'cms_page.status', 'cms_redirect.status_code', 'cms_redirect.is_enabled'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_attribute
       WHERE attrelid = to_regclass('public.' || split_part(col, '.', 1))
         AND attname = split_part(col, '.', 2) AND NOT attisdropped
    ) THEN
      RAISE EXCEPTION 'Column % not found: these tables are not the stray design this repair expects. Nothing changed.', col;
    END IF;
  END LOOP;

  CREATE SCHEMA cms_stray_0003;
  COMMENT ON SCHEMA cms_stray_0003 IS
    'CMS tables from the uncommitted migration cms.0003_pages_nav_seo (5 Nov 2026), moved aside on repair; kept, not used by the app.';
  ALTER TABLE public.cms_seorecord SET SCHEMA cms_stray_0003;
  ALTER TABLE public.cms_navigationitem SET SCHEMA cms_stray_0003;
  ALTER TABLE public.cms_page SET SCHEMA cms_stray_0003;
  ALTER TABLE public.cms_redirect SET SCHEMA cms_stray_0003;
  RAISE NOTICE 'Moved the four stray CMS tables to schema cms_stray_0003. Now run migrate (start Docker Compose).';
END
$repair$;

COMMIT;
