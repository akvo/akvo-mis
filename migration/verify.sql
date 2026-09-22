-- Post-import assertions.  MT-014.
--
-- Included by import.sql while still inside the transaction, so a failure
-- here aborts before anything is committed.  Every check raises rather
-- than warns: a migration that half-worked is worse than one that did not
-- run, because the damage is discovered weeks later by a user.
--
-- Reads mig.tenant_id and mig.offset, set by import.sql -- psql does not
-- interpolate :variables inside dollar-quoted bodies.

\echo ''
\echo '--- verification ---'


-- 1. Row counts: every source row landed, scoped by its TENANT_PATH.
DO $counts$
DECLARE
    t    bigint := current_setting('mig.tenant_id')::bigint;
    rec  record;
    bad  text := '';
BEGIN
    FOR rec IN
        WITH expected(label, n) AS (
            SELECT 'levels',                             count(*) FROM mig_src.levels
            UNION ALL SELECT 'organisation',             count(*) FROM mig_src.organisation
            UNION ALL SELECT 'administrator',            count(*) FROM mig_src.administrator
            UNION ALL SELECT 'form',                     count(*) FROM mig_src.form
            UNION ALL SELECT 'question_group',           count(*) FROM mig_src.question_group
            UNION ALL SELECT 'question',                 count(*) FROM mig_src.question
            UNION ALL SELECT 'option',                   count(*) FROM mig_src.option
            UNION ALL SELECT 'form_published_version',   count(*) FROM mig_src.form_published_version
            UNION ALL SELECT 'user_form',                count(*) FROM mig_src.user_form
            UNION ALL SELECT 'data',                     count(*) FROM mig_src.data
            UNION ALL SELECT 'answer',                   count(*) FROM mig_src.answer
            UNION ALL SELECT 'mobile_assignments',       count(*) FROM mig_src.mobile_assignments
            UNION ALL SELECT 'mobile_assignments_forms', count(*) FROM mig_src.mobile_assignments_forms
            UNION ALL SELECT 'mobile_assignments_administrations', count(*) FROM mig_src.mobile_assignments_administrations
        ),
        actual(label, n) AS (
            SELECT 'levels',           count(*) FROM public.levels WHERE tenant_id = t
            UNION ALL SELECT 'organisation',  count(*) FROM public.organisation WHERE tenant_id = t
            UNION ALL SELECT 'administrator', count(*) FROM public.administrator WHERE tenant_id = t
            UNION ALL SELECT 'form',          count(*) FROM public.form WHERE tenant_id = t
            UNION ALL SELECT 'question_group', count(*) FROM public.question_group g
                 JOIN public.form f ON f.id = g.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'question', count(*) FROM public.question q
                 JOIN public.form f ON f.id = q.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'option', count(*) FROM public.option o
                 JOIN public.question q ON q.id = o.question_id
                 JOIN public.form f ON f.id = q.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'form_published_version', count(*) FROM public.form_published_version v
                 JOIN public.form f ON f.id = v.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'user_form', count(*) FROM public.user_form uf
                 JOIN public.form f ON f.id = uf.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'data', count(*) FROM public.data d
                 JOIN public.form f ON f.id = d.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'answer', count(*) FROM public.answer a
                 JOIN public.data d ON d.id = a.data_id
                 JOIN public.form f ON f.id = d.form_id WHERE f.tenant_id = t
            UNION ALL SELECT 'mobile_assignments', count(*) FROM public.mobile_assignments ma
                 JOIN public.system_user u ON u.id = ma.user_id WHERE u.tenant_id = t
            UNION ALL SELECT 'mobile_assignments_forms', count(*) FROM public.mobile_assignments_forms maf
                 JOIN public.mobile_assignments ma ON ma.id = maf.mobileassignment_id
                 JOIN public.system_user u ON u.id = ma.user_id WHERE u.tenant_id = t
            UNION ALL SELECT 'mobile_assignments_administrations', count(*) FROM public.mobile_assignments_administrations maa
                 JOIN public.mobile_assignments ma ON ma.id = maa.mobileassignment_id
                 JOIN public.system_user u ON u.id = ma.user_id WHERE u.tenant_id = t
        )
        SELECT e.label, e.n AS expected, a.n AS actual
        FROM expected e JOIN actual a USING (label)
        WHERE e.n IS DISTINCT FROM a.n
    LOOP
        bad := bad || format('%s: expected %s, found %s; ', rec.label, rec.expected, rec.actual);
    END LOOP;

    IF bad <> '' THEN
        RAISE EXCEPTION 'Row count mismatch -- %', bad;
    END IF;
    RAISE NOTICE 'row counts match for all 14 counted tables';
END
$counts$;


-- 2. Every source account resolves to a row in this workspace, whether it
--    was inserted or reconciled onto an existing one.
DO $users$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    SELECT count(*) INTO n
    FROM mig_src._user_map m
    LEFT JOIN public.system_user u ON u.id = m.dst_id AND u.tenant_id = t
    WHERE u.id IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION '% source account(s) do not resolve to a user in workspace %', n, t;
    END IF;

    SELECT count(*) INTO n FROM mig_src._user_map WHERE NOT do_insert;
    IF n > 0 THEN
        RAISE NOTICE '% source account(s) reconciled onto existing users (duplicate email)', n;
    END IF;
END
$users$;


-- 3. unique_email_per_tenant holds.  The constraint would catch this at
--    COMMIT, but naming it here makes the failure legible.
DO $emails$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    SELECT count(*) INTO n FROM (
        SELECT lower(email) FROM public.system_user WHERE tenant_id = t
        GROUP BY lower(email) HAVING count(*) > 1
    ) x;
    IF n > 0 THEN
        RAISE EXCEPTION '% duplicated email address(es) in workspace %', n, t;
    END IF;
END
$emails$;


-- 4. administrator.path.  The offset rewrites these component by
--    component; a mistake leaves every row inserted and the whole tree
--    pointing nowhere, which no foreign key would catch.
DO $paths$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    -- Every component of every path names an administration in this
    -- workspace.
    SELECT count(*) INTO n
    FROM public.administrator a
    CROSS JOIN LATERAL unnest(string_to_array(rtrim(a.path, '.'), '.')) AS part
    WHERE a.tenant_id = t
      AND a.path IS NOT NULL AND a.path <> ''
      AND NOT EXISTS (
          SELECT 1 FROM public.administrator p
          WHERE p.id = part::bigint AND p.tenant_id = t
      );
    IF n > 0 THEN
        RAISE EXCEPTION '% administration path component(s) do not resolve inside workspace %', n, t;
    END IF;

    -- A non-root row's path ends with its own parent.
    SELECT count(*) INTO n
    FROM public.administrator a
    WHERE a.tenant_id = t
      AND a.parent_id IS NOT NULL
      AND split_part(rtrim(a.path, '.'), '.', array_length(string_to_array(rtrim(a.path, '.'), '.'), 1))::bigint
          IS DISTINCT FROM a.parent_id;
    IF n > 0 THEN
        RAISE EXCEPTION '% administration path(s) disagree with their parent_id in workspace %', n, t;
    END IF;

    -- Exactly one root, which the partial unique index also enforces.
    SELECT count(*) INTO n FROM public.administrator WHERE tenant_id = t AND parent_id IS NULL;
    IF n <> 1 THEN
        RAISE EXCEPTION 'workspace % has % root administrations, expected 1', t, n;
    END IF;
    RAISE NOTICE 'administration paths resolve';
END
$paths$;


-- 5. Nothing imported points outside the workspace.
DO $orphans$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    SELECT count(*) INTO n
    FROM public.data d
    JOIN public.form f ON f.id = d.form_id
    JOIN public.administrator a ON a.id = d.administration_id
    WHERE f.tenant_id = t AND a.tenant_id IS DISTINCT FROM t;
    IF n > 0 THEN
        RAISE EXCEPTION '% submission(s) reference an administration outside workspace %', n, t;
    END IF;

    SELECT count(*) INTO n
    FROM public.data d
    JOIN public.form f ON f.id = d.form_id
    JOIN public.system_user u ON u.id = d.created_by_id
    WHERE f.tenant_id = t AND u.tenant_id IS DISTINCT FROM t;
    IF n > 0 THEN
        RAISE EXCEPTION '% submission(s) credited to a user outside workspace %', n, t;
    END IF;

    -- A monitoring submission's parent must be in the same workspace.
    SELECT count(*) INTO n
    FROM public.data d
    JOIN public.form f ON f.id = d.form_id
    JOIN public.data p ON p.id = d.parent_id
    JOIN public.form pf ON pf.id = p.form_id
    WHERE f.tenant_id = t AND pf.tenant_id IS DISTINCT FROM t;
    IF n > 0 THEN
        RAISE EXCEPTION '% submission(s) have a parent outside workspace %', n, t;
    END IF;
    RAISE NOTICE 'no cross-workspace references';
END
$orphans$;


-- 6. The other workspaces are exactly as we found them.
DO $others$
DECLARE
    t bigint := current_setting('mig.tenant_id')::bigint;
    n bigint;
BEGIN
    WITH after_ AS (
        SELECT tenant_id, count(*) AS n FROM public.system_user
         WHERE tenant_id IS DISTINCT FROM t GROUP BY tenant_id
        UNION ALL
        SELECT tenant_id, count(*) FROM public.form
         WHERE tenant_id IS DISTINCT FROM t GROUP BY tenant_id
        UNION ALL
        SELECT f.tenant_id, count(*) FROM public.data d JOIN public.form f ON f.id = d.form_id
         WHERE f.tenant_id IS DISTINCT FROM t GROUP BY f.tenant_id
    )
    SELECT count(*) INTO n FROM (
        (SELECT * FROM mig_src._others_before EXCEPT ALL SELECT * FROM after_)
        UNION ALL
        (SELECT * FROM after_ EXCEPT ALL SELECT * FROM mig_src._others_before)
    ) diff;
    IF n > 0 THEN
        RAISE EXCEPTION 'other workspaces changed -- % differing count group(s)', n;
    END IF;
    RAISE NOTICE 'other workspaces untouched';
END
$others$;


-- 7. Sequences are past everything we inserted, so the next application
--    write does not collide with a migrated row.
DO $seqs$
DECLARE
    rec     record;
    behind  int;
    bad     text := '';
BEGIN
    FOR rec IN
        SELECT t AS tbl FROM unnest(ARRAY[
            'levels','organisation','administrator','system_user','option',
            'form_published_version','user_form','data','answer',
            'mobile_assignments','mobile_assignments_forms',
            'mobile_assignments_administrations']) AS t
    LOOP
        EXECUTE format(
            'SELECT CASE WHEN (SELECT last_value FROM public.%I) < COALESCE((SELECT max(id) FROM public.%I), 0)
                    THEN 1 ELSE 0 END', rec.tbl || '_id_seq', rec.tbl)
        INTO behind;
        IF behind = 1 THEN
            bad := bad || rec.tbl || ' ';
        END IF;
    END LOOP;
    IF bad <> '' THEN
        RAISE EXCEPTION 'sequence behind max(id) for: %', bad;
    END IF;
    RAISE NOTICE 'sequences advanced';
END
$seqs$;


-- Summary, printed whether this is a dry run or the real thing.
\echo ''
\echo 'workspace contents after import:'
SELECT 'form'          AS entity, count(*) FROM public.form  WHERE tenant_id = (current_setting('mig.tenant_id')::bigint)
UNION ALL SELECT 'administration', count(*) FROM public.administrator WHERE tenant_id = (current_setting('mig.tenant_id')::bigint)
UNION ALL SELECT 'user',           count(*) FROM public.system_user   WHERE tenant_id = (current_setting('mig.tenant_id')::bigint)
UNION ALL SELECT 'submission',     count(*) FROM public.data d JOIN public.form f ON f.id = d.form_id
                                    WHERE f.tenant_id = (current_setting('mig.tenant_id')::bigint)
UNION ALL SELECT 'answer',         count(*) FROM public.answer a JOIN public.data d ON d.id = a.data_id
                                    JOIN public.form f ON f.id = d.form_id
                                    WHERE f.tenant_id = (current_setting('mig.tenant_id')::bigint);
