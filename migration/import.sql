-- Import a single-host install's rows into one workspace.  MT-014.
--
-- Runs as ONE transaction.  Either the workspace is whole afterwards or
-- nothing happened.  Driven by migrate-tenant.sh, which validates the
-- arguments and builds :copy_data; running this file by hand is possible
-- but the shell is the supported entry point.
--
-- Required psql variables:
--   tenant_id  the target workspace's tenant.id, already validated
--   copy_data  path to the extracted COPY blocks, rewritten to mig_src.*
--   sql_dir    directory holding verify.sql
--   do_reset   on|off  -- delete everything the workspace owns first
--   dry_run    on|off  -- roll back instead of committing

\set ON_ERROR_STOP on

BEGIN;

-- Django declares every FK DEFERRABLE INITIALLY DEFERRED, so insert order
-- inside the transaction does not matter.  Said explicitly because the
-- circular pair form.active_version_id <-> form_published_version.form_id
-- has no valid order, and because the reset below deletes parents and
-- children in whatever order reads most clearly.
SET CONSTRAINTS ALL DEFERRED;

-- current_setting() is how the DO blocks below reach these: psql does not
-- interpolate :variables inside dollar-quoted bodies.
SELECT set_config('mig.tenant_id', :'tenant_id', true);
SELECT set_config('mig.do_reset', :'do_reset', true);


-- ---------------------------------------------------------------------
-- 1. Refuse a workspace that already holds data, unless --reset
-- ---------------------------------------------------------------------
-- Without this the second run of a rehearsal silently doubles the
-- workspace.  Forms are the probe because every migration creates some
-- and nothing else does.

DO $guard$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.tenant WHERE id = t) THEN
        RAISE EXCEPTION 'No workspace with tenant id %', t;
    END IF;

    SELECT count(*) INTO n FROM public.form WHERE tenant_id = t;
    IF n > 0 AND NOT current_setting('mig.do_reset')::boolean THEN
        RAISE EXCEPTION
            'Workspace % already holds % form(s). Re-run with --reset to replace it.', t, n;
    END IF;
END
$guard$;


-- ---------------------------------------------------------------------
-- 2. Snapshot the other workspaces, so the verify step can prove we did
--    not touch them
-- ---------------------------------------------------------------------

CREATE SCHEMA mig_src;

CREATE TABLE mig_src._others_before AS
SELECT tenant_id, count(*) AS n FROM public.system_user
 WHERE tenant_id IS DISTINCT FROM :tenant_id GROUP BY tenant_id
UNION ALL
SELECT tenant_id, count(*) FROM public.form
 WHERE tenant_id IS DISTINCT FROM :tenant_id GROUP BY tenant_id
UNION ALL
SELECT f.tenant_id, count(*) FROM public.data d JOIN public.form f ON f.id = d.form_id
 WHERE f.tenant_id IS DISTINCT FROM :tenant_id GROUP BY f.tenant_id;


-- ---------------------------------------------------------------------
-- 3. Reset (total -- MT-014 D-9)
-- ---------------------------------------------------------------------
-- Everything the workspace owns goes, the tenant row aside.  Nothing is
-- special-cased, so this is a clean inverse of the import and there is no
-- "which account survives?" branch to get wrong.  A superadmin is
-- recreated afterwards with:
--     ./manage.py createsuperuser --tenant=<subdomain>
--
-- Children first, though DEFERRED constraints make that a readability
-- choice rather than a requirement.

\if :do_reset

DELETE FROM public.answer_history WHERE data_id IN
    (SELECT d.id FROM public.data d JOIN public.form f ON f.id = d.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.answer WHERE data_id IN
    (SELECT d.id FROM public.data d JOIN public.form f ON f.id = d.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.batch_data WHERE batch_id IN
    (SELECT b.id FROM public.batch b JOIN public.form f ON f.id = b.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.batch_comment WHERE batch_id IN
    (SELECT b.id FROM public.batch b JOIN public.form f ON f.id = b.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.batch_attachment WHERE batch_id IN
    (SELECT b.id FROM public.batch b JOIN public.form f ON f.id = b.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.data_approval WHERE batch_id IN
    (SELECT b.id FROM public.batch b JOIN public.form f ON f.id = b.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.batch WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);
DELETE FROM public.data WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);

DELETE FROM public.question_attribute WHERE question_id IN
    (SELECT q.id FROM public.question q JOIN public.form f ON f.id = q.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.option WHERE question_id IN
    (SELECT q.id FROM public.question q JOIN public.form f ON f.id = q.form_id WHERE f.tenant_id = :tenant_id);
DELETE FROM public.dashboard_widget WHERE dashboard_id IN
    (SELECT id FROM public.dashboard WHERE tenant_id = :tenant_id);
DELETE FROM public.dashboard WHERE tenant_id = :tenant_id;
DELETE FROM public.question WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);
DELETE FROM public.question_group WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);
DELETE FROM public.form_published_version WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);
DELETE FROM public.user_form WHERE form_id IN (SELECT id FROM public.form WHERE tenant_id = :tenant_id);

DELETE FROM public.mobile_assignments_forms WHERE mobileassignment_id IN
    (SELECT m.id FROM public.mobile_assignments m JOIN public.system_user u ON u.id = m.user_id WHERE u.tenant_id = :tenant_id);
DELETE FROM public.mobile_assignments_administrations WHERE mobileassignment_id IN
    (SELECT m.id FROM public.mobile_assignments m JOIN public.system_user u ON u.id = m.user_id WHERE u.tenant_id = :tenant_id);
DELETE FROM public.mobile_assignments WHERE user_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);

DELETE FROM public.form WHERE tenant_id = :tenant_id;

DELETE FROM public.entity_data WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tenant_id);
DELETE FROM public.entities WHERE tenant_id = :tenant_id;

DELETE FROM public.administration_attribute_value WHERE attribute_id IN
    (SELECT id FROM public.administration_attribute WHERE tenant_id = :tenant_id);
DELETE FROM public.administration_attribute WHERE tenant_id = :tenant_id;

DELETE FROM public.user_role WHERE user_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);
DELETE FROM public.role_access WHERE role_id IN (SELECT id FROM public.role WHERE tenant_id = :tenant_id);
DELETE FROM public.role_feature_access WHERE role_id IN (SELECT id FROM public.role WHERE tenant_id = :tenant_id);
DELETE FROM public.role WHERE tenant_id = :tenant_id;

DELETE FROM public.jobs WHERE user_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);
DELETE FROM public.django_admin_log WHERE user_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);
DELETE FROM public.system_user_groups WHERE systemuser_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);
DELETE FROM public.system_user_user_permissions WHERE systemuser_id IN (SELECT id FROM public.system_user WHERE tenant_id = :tenant_id);
DELETE FROM public.system_user WHERE tenant_id = :tenant_id;

DELETE FROM public.organisation_attribute WHERE organisation_id IN
    (SELECT id FROM public.organisation WHERE tenant_id = :tenant_id);
DELETE FROM public.organisation WHERE tenant_id = :tenant_id;

DELETE FROM public.administrator WHERE tenant_id = :tenant_id;
DELETE FROM public.levels WHERE tenant_id = :tenant_id;

\endif


-- ---------------------------------------------------------------------
-- 4. Staging tables, cloned from the TARGET (MT-014 D-2)
-- ---------------------------------------------------------------------
-- Cloned rather than replayed from the dump's own DDL, so a dump taken
-- against a different Postgres major version loads regardless -- the dump
-- is consumed as data, never as DDL.  LIKE copies columns, types and NOT
-- NULL but no keys or FKs, so the COPY blocks load in any order.

CREATE TABLE mig_src.levels                             (LIKE public.levels);
CREATE TABLE mig_src.organisation                       (LIKE public.organisation);
CREATE TABLE mig_src.administrator                      (LIKE public.administrator);
CREATE TABLE mig_src.system_user                        (LIKE public.system_user);
CREATE TABLE mig_src.form                               (LIKE public.form);
CREATE TABLE mig_src.question_group                     (LIKE public.question_group);
CREATE TABLE mig_src.question                           (LIKE public.question);
CREATE TABLE mig_src.option                             (LIKE public.option);
CREATE TABLE mig_src.form_published_version             (LIKE public.form_published_version);
CREATE TABLE mig_src.user_form                          (LIKE public.user_form);
CREATE TABLE mig_src.data                               (LIKE public.data);
CREATE TABLE mig_src.answer                             (LIKE public.answer);
CREATE TABLE mig_src.mobile_assignments                 (LIKE public.mobile_assignments);
CREATE TABLE mig_src.mobile_assignments_forms           (LIKE public.mobile_assignments_forms);
CREATE TABLE mig_src.mobile_assignments_administrations (LIKE public.mobile_assignments_administrations);

-- The one column the source predates that the target requires.  It is NOT
-- NULL with no database default, and the source's COPY simply omits it,
-- so staging needs a default for the load to succeed.  true, because the
-- migrated accounts must be able to sign in immediately.
ALTER TABLE mig_src.system_user ALTER COLUMN is_active SET DEFAULT true;


-- ---------------------------------------------------------------------
-- 5. Load the source rows
-- ---------------------------------------------------------------------
-- COPY blocks extracted from the dump by migrate-tenant.sh, with their
-- schema prefix rewritten.  Tables absent from the staging schema above
-- were never extracted, which is how jobs, mobile_apks and the django_*
-- operational tables are excluded -- by omission, not by filtering rows.

\i :copy_data


-- ---------------------------------------------------------------------
-- 6. The ID offset (MT-014 D-3)
-- ---------------------------------------------------------------------
-- One constant for every remapped table, computed from the target's
-- current high-water mark and rounded up to the next 10 million.  Source
-- IDs are small, so a single number keeps every migrated row's provenance
-- visible in its ID and keeps the statements below reviewable.
--
-- form, question and question_group are NOT offset: their keys are
-- epoch-millisecond values that deployed mobile clients and stored form
-- JSON reference directly (D-5).

SELECT ((GREATEST(
            (SELECT COALESCE(max(id), 0) FROM public.levels),
            (SELECT COALESCE(max(id), 0) FROM public.organisation),
            (SELECT COALESCE(max(id), 0) FROM public.administrator),
            (SELECT COALESCE(max(id), 0) FROM public.system_user),
            (SELECT COALESCE(max(id), 0) FROM public.option),
            (SELECT COALESCE(max(id), 0) FROM public.form_published_version),
            (SELECT COALESCE(max(id), 0) FROM public.user_form),
            (SELECT COALESCE(max(id), 0) FROM public.data),
            (SELECT COALESCE(max(id), 0) FROM public.answer),
            (SELECT COALESCE(max(id), 0) FROM public.mobile_assignments),
            (SELECT COALESCE(max(id), 0) FROM public.mobile_assignments_forms),
            (SELECT COALESCE(max(id), 0) FROM public.mobile_assignments_administrations)
        ) / 10000000)::bigint + 1) * 10000000 AS v_offset
\gset

SELECT set_config('mig.offset', :'v_offset', true);


-- ---------------------------------------------------------------------
-- 7. Reconcile duplicate accounts (MT-014 FR-10 / D-6)
-- ---------------------------------------------------------------------
-- unique_email_per_tenant is on (email, tenant_id), so a source account
-- whose address already exists under this workspace cannot be inserted.
-- It is skipped and its references are repointed at the surviving row.
-- Found by query, never by a hardcoded list.

CREATE TABLE mig_src._user_map AS
SELECT s.id                                   AS src_id,
       COALESCE(t.id, s.id + :v_offset)       AS dst_id,
       (t.id IS NULL)                         AS do_insert
FROM mig_src.system_user s
LEFT JOIN public.system_user t
       ON lower(t.email) = lower(s.email)
      AND t.tenant_id = :tenant_id;


-- ---------------------------------------------------------------------
-- 8. Insert, in dependency order
-- ---------------------------------------------------------------------

INSERT INTO public.levels (id, name, level, tenant_id)
SELECT id + :v_offset, name, level, :tenant_id
FROM mig_src.levels;

INSERT INTO public.organisation (id, name, tenant_id)
SELECT id + :v_offset, name, :tenant_id
FROM mig_src.organisation;

-- administrator.path encodes ancestry as a dot-terminated ID trail
-- ("7254.7255.7256."), so it has to be rewritten component by component in
-- lockstep with the offset.  Get this wrong and the hierarchy breaks
-- silently -- every row still inserts, the tree just points nowhere.
-- The root's path is NULL or empty; the lateral yields no row for it and
-- COALESCE passes the original through untouched.
INSERT INTO public.administrator (id, code, name, path, level_id, parent_id, tenant_id)
SELECT a.id + :v_offset,
       a.code,
       a.name,
       COALESCE(np.new_path, a.path),
       a.level_id + :v_offset,
       a.parent_id + :v_offset,
       :tenant_id
FROM mig_src.administrator a
LEFT JOIN LATERAL (
    SELECT string_agg((e.part::bigint + :v_offset)::text, '.' ORDER BY e.ord) || '.' AS new_path
    FROM unnest(string_to_array(rtrim(a.path, '.'), '.')) WITH ORDINALITY AS e(part, ord)
    WHERE a.path IS NOT NULL AND a.path <> ''
) np ON true;

INSERT INTO public.system_user (
    id, password, last_login, is_superuser, deleted_at, email, date_joined,
    first_name, last_name, phone_number, trained, updated, organisation_id,
    tenant_id, is_active)
SELECT m.dst_id, s.password, s.last_login, s.is_superuser, s.deleted_at, s.email,
       s.date_joined, s.first_name, s.last_name, s.phone_number, s.trained,
       s.updated, s.organisation_id + :v_offset, :tenant_id, s.is_active
FROM mig_src.system_user s
JOIN mig_src._user_map m ON m.src_id = s.id
WHERE m.do_insert;

-- form.id preserved.  active_version_id points at form_published_version,
-- which IS offset; parent_id and previous_version_id point at form, which
-- is not.
INSERT INTO public.form (
    id, name, version, uuid, approval_instructions, type, parent_id, created,
    created_by_id, default_language, description, languages, previous_version_id,
    published_at, status, translations, updated, updated_by_id, active_version_id,
    deleted_at, tenant_id)
SELECT f.id, f.name, f.version, f.uuid, f.approval_instructions, f.type, f.parent_id,
       f.created, cb.dst_id, f.default_language, f.description, f.languages,
       f.previous_version_id, f.published_at, f.status, f.translations, f.updated,
       ub.dst_id, f.active_version_id + :v_offset, f.deleted_at, :tenant_id
FROM mig_src.form f
LEFT JOIN mig_src._user_map cb ON cb.src_id = f.created_by_id
LEFT JOIN mig_src._user_map ub ON ub.src_id = f.updated_by_id;

INSERT INTO public.question_group (
    id, name, label, "order", repeatable, repeat_text, form_id, deleted_at, translations)
SELECT id, name, label, "order", repeatable, repeat_text, form_id, deleted_at, translations
FROM mig_src.question_group;

INSERT INTO public.question (
    id, "order", label, short_label, name, type, meta, required, rule, dependency,
    api, extra, tooltip, fn, pre, display_only, form_id, question_group_id,
    dependency_rule, addon_after, addon_before, center, data_api_url, deleted_at,
    disabled, hidden_string, required_double_entry, translations, variable_name,
    tree_option, "limit", columns)
SELECT id, "order", label, short_label, name, type, meta, required, rule, dependency,
       api, extra, tooltip, fn, pre, display_only, form_id, question_group_id,
       dependency_rule, addon_after, addon_before, center, data_api_url, deleted_at,
       disabled, hidden_string, required_double_entry, translations, variable_name,
       tree_option, "limit", columns
FROM mig_src.question;

-- answer.options stores option *values* and geo coordinates as strings,
-- never option IDs, so offsetting option.id here is safe.
INSERT INTO public.option (id, "order", label, value, other, color, question_id, translations)
SELECT id + :v_offset, "order", label, value, other, color, question_id, translations
FROM mig_src.option;

INSERT INTO public.form_published_version (id, version, schema, published_at, form_id, published_by_id)
SELECT v.id + :v_offset, v.version, v.schema, v.published_at, v.form_id, pb.dst_id
FROM mig_src.form_published_version v
LEFT JOIN mig_src._user_map pb ON pb.src_id = v.published_by_id;

INSERT INTO public.user_form (id, form_id, user_id)
SELECT uf.id + :v_offset, uf.form_id, m.dst_id
FROM mig_src.user_form uf
JOIN mig_src._user_map m ON m.src_id = uf.user_id;

INSERT INTO public.data (
    id, deleted_at, name, geo, uuid, created, updated, duration, submitter,
    is_pending, administration_id, created_by_id, form_id, parent_id,
    updated_by_id, is_draft, published_version_id, submission_key)
SELECT d.id + :v_offset, d.deleted_at, d.name, d.geo, d.uuid, d.created, d.updated,
       d.duration, d.submitter, d.is_pending, d.administration_id + :v_offset,
       cb.dst_id, d.form_id, d.parent_id + :v_offset, ub.dst_id, d.is_draft,
       d.published_version_id + :v_offset, d.submission_key
FROM mig_src.data d
LEFT JOIN mig_src._user_map cb ON cb.src_id = d.created_by_id
LEFT JOIN mig_src._user_map ub ON ub.src_id = d.updated_by_id;

INSERT INTO public.answer (
    id, name, value, options, created, updated, index, created_by_id, data_id, question_id)
SELECT a.id + :v_offset, a.name, a.value, a.options, a.created, a.updated, a.index,
       cb.dst_id, a.data_id + :v_offset, a.question_id
FROM mig_src.answer a
LEFT JOIN mig_src._user_map cb ON cb.src_id = a.created_by_id;

INSERT INTO public.mobile_assignments (id, name, passcode, token, created_at, last_synced_at, user_id)
SELECT ma.id + :v_offset, ma.name, ma.passcode, ma.token, ma.created_at, ma.last_synced_at, m.dst_id
FROM mig_src.mobile_assignments ma
JOIN mig_src._user_map m ON m.src_id = ma.user_id;

INSERT INTO public.mobile_assignments_forms (id, mobileassignment_id, forms_id)
SELECT id + :v_offset, mobileassignment_id + :v_offset, forms_id
FROM mig_src.mobile_assignments_forms;

INSERT INTO public.mobile_assignments_administrations (id, mobileassignment_id, administration_id)
SELECT id + :v_offset, mobileassignment_id + :v_offset, administration_id + :v_offset
FROM mig_src.mobile_assignments_administrations;


-- ---------------------------------------------------------------------
-- 9. Advance the sequences past what we inserted
-- ---------------------------------------------------------------------
-- Only the offset tables.  form, question and question_group keep their
-- source keys and never allocated from their sequences, so those are left
-- where the application had them.

SELECT setval('public.levels_id_seq',                             GREATEST((SELECT COALESCE(max(id),1) FROM public.levels), 1));
SELECT setval('public.organisation_id_seq',                       GREATEST((SELECT COALESCE(max(id),1) FROM public.organisation), 1));
SELECT setval('public.administrator_id_seq',                      GREATEST((SELECT COALESCE(max(id),1) FROM public.administrator), 1));
SELECT setval('public.system_user_id_seq',                        GREATEST((SELECT COALESCE(max(id),1) FROM public.system_user), 1));
SELECT setval('public.option_id_seq',                             GREATEST((SELECT COALESCE(max(id),1) FROM public.option), 1));
SELECT setval('public.form_published_version_id_seq',             GREATEST((SELECT COALESCE(max(id),1) FROM public.form_published_version), 1));
SELECT setval('public.user_form_id_seq',                          GREATEST((SELECT COALESCE(max(id),1) FROM public.user_form), 1));
SELECT setval('public.data_id_seq',                               GREATEST((SELECT COALESCE(max(id),1) FROM public.data), 1));
SELECT setval('public.answer_id_seq',                             GREATEST((SELECT COALESCE(max(id),1) FROM public.answer), 1));
SELECT setval('public.mobile_assignments_id_seq',                 GREATEST((SELECT COALESCE(max(id),1) FROM public.mobile_assignments), 1));
SELECT setval('public.mobile_assignments_forms_id_seq',           GREATEST((SELECT COALESCE(max(id),1) FROM public.mobile_assignments_forms), 1));
SELECT setval('public.mobile_assignments_administrations_id_seq', GREATEST((SELECT COALESCE(max(id),1) FROM public.mobile_assignments_administrations), 1));


-- ---------------------------------------------------------------------
-- 10. Prove it before committing
-- ---------------------------------------------------------------------

\i :verify_sql

DROP SCHEMA mig_src CASCADE;

\if :dry_run
\echo ''
\echo '*** DRY RUN -- rolling back. Nothing was written. ***'
ROLLBACK;
\else
COMMIT;
\echo ''
\echo '*** Committed. ***'
\endif
