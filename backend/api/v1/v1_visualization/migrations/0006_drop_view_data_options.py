from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("v1_data", "0006_purge_server_drafts"),
        ("v1_visualization", "0005_alter_dashboardwidget_type"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP MATERIALIZED VIEW IF EXISTS view_data_options;",
            reverse_sql="""
            CREATE MATERIALIZED VIEW view_data_options as
                SELECT
                    row_number() over (partition by true) as id,
                    d.parent_id as parent_data_id,
                    tmp.data_id,
                    d.administration_id,
                    d.form_id,
                    to_jsonb(array_agg(
                        concat(tmp.question_id, '||',
                            lower(tmp.option_ids::text))
                    )) as options
                FROM (
                    SELECT
                        a.data_id,
                        a.question_id,
                        a.id as answer_id,
                        jsonb_agg(qo.id) as option_ids
                    FROM answer a
                    LEFT JOIN question q on q.id = a.question_id
                    LEFT JOIN option qo ON qo.question_id = a.question_id
                        AND qo.value = ANY(SELECT jsonb_array_elements_text(a.options))
                    WHERE (q.type = 5 OR q.type = 6) AND a.options IS NOT NULL
                    GROUP BY a.data_id, a.question_id, a.id
                ) tmp
                LEFT JOIN (
                    SELECT *,
                        ROW_NUMBER() OVER (PARTITION BY parent_id, form_id ORDER BY created DESC) as rn
                    FROM data
                    WHERE parent_id IS NOT NULL
                        AND is_pending = FALSE
                ) d ON d.id = tmp.data_id AND d.rn = 1
                LEFT JOIN form f ON f.id = d.form_id
                WHERE f.parent_id IS NOT NULL
                GROUP BY tmp.data_id, d.administration_id, d.form_id, d.parent_id;
            """,
        ),
    ]
