import os
import sqlite3
import time
import pandas as pd
import logging
from django.conf import settings
from mis.settings import MASTER_DATA, STORAGE_PATH, COUNTRY_NAME
from api.v1.v1_profile.models import Administration

logger = logging.getLogger(__name__)


# Master data is offline data: whatever lands in these files is what a
# device holds on its own storage. One global file per table therefore
# handed every device every tenant's hierarchy, so each tenant gets its
# own subdirectory keyed by subdomain. tenant=None keeps the historical
# root location for seeders and the management command.
def sqlite_path(model, tenant=None, test: bool = False):
    if not test:
        test = settings.TEST_ENV
    directory = (
        MASTER_DATA
        if tenant is None
        else "{0}/{1}".format(MASTER_DATA, tenant.subdomain)
    )
    return "{0}/{1}{2}.sqlite".format(
        directory,
        "test_" if test else "",
        model._meta.db_table,
    )


def generate_sqlite(model, tenant=None, test: bool = False):
    if not test:
        test = settings.TEST_ENV
    field_names = [f.name for f in model._meta.fields]
    objects = model.objects.all()
    if tenant is not None:
        objects = objects.filter(**{model.TENANT_PATH: tenant})
    file_name = sqlite_path(model, tenant=tenant, test=test)
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    if os.path.exists(file_name):
        try:
            os.remove(file_name)
        except OSError:
            pass
    # columns= keeps the frame's shape when a tenant has no rows yet, so an
    # empty tenant still gets a valid nodes table rather than no file: the
    # device asks for entity_data.sqlite whether or not entities exist.
    data = pd.DataFrame(
        list(objects.values(*field_names)), columns=field_names
    )
    # Add full_path_name for Administration model
    if model.__name__ == "Administration":
        # Get all Administration objects with their full_path_name property
        full_path_names = {
            obj.id: obj.full_path_name.replace("|", " - ") for obj in objects
        }
        # Add the full_path_name column to the DataFrame
        data["full_path_name"] = data["id"].apply(
            lambda id_: full_path_names.get(id_, "")
        )

    if "parent" in field_names:
        data["parent"] = data["parent"].apply(
            lambda x: int(x) if x == x else 0
        )
    elif "administration" in field_names:
        data["parent"] = data["administration"].apply(
            lambda x: int(x) if x == x else 0
        )
    else:
        data["parent"] = 0
    last_err = None
    for attempt in range(5):
        try:
            conn = sqlite3.connect(file_name, timeout=30)
            try:
                data.to_sql("nodes", conn, if_exists="replace", index=False)
            finally:
                conn.close()
            return file_name
        except sqlite3.OperationalError as err:
            last_err = err
            time.sleep(0.1 * (2 ** attempt))
    raise last_err


def update_sqlite(model, data, tenant=None, id=None):
    test = settings.TEST_ENV
    fields = data.keys()
    field_names = ", ".join([f for f in fields])
    placeholders = ", ".join(["?" for _ in range(len(fields))])
    update_placeholders = ", ".join([f"{f} = ?" for f in fields])
    params = list(data.values())
    if id:
        params += [id]
    file_name = sqlite_path(model, tenant=tenant, test=test)
    # sqlite3.connect creates the file but not its parent directory, and a
    # tenant's first row can arrive before anything generated the file.
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    conn = sqlite3.connect(file_name, timeout=30)
    try:
        with conn:
            c = conn.cursor()
            if id:
                c.execute("SELECT * FROM nodes WHERE id = ?", (id,))
                if c.fetchone():
                    query = f"UPDATE nodes \
                        SET {update_placeholders} WHERE id = ?"
                    c.execute(query, params)
            if not id:
                query = f"INSERT INTO nodes({field_names}) \
                    VALUES ({placeholders})"
                c.execute(query, params)
    except sqlite3.OperationalError:
        generate_sqlite(model=model, tenant=tenant, test=test)
    finally:
        conn.close()


def administration_csv_add(data: dict):
    test = settings.TEST_ENV
    filename = "{0}-administration.csv".format(
        "test" if test else COUNTRY_NAME
    )
    filepath = f"{STORAGE_PATH}/master_data/{filename}"
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        new_data = {}
        if data.path:
            parent_ids = list(filter(lambda path: path, data.path.split(".")))
            parents = Administration.objects.filter(
                pk__in=parent_ids, level__id__gt=1
            ).all()
            for p in parents:
                new_data[p.level.name.lower()] = p.name
                new_data[f"{p.level.name.lower()}_id"] = p.id
        new_data[data.level.name.lower()] = data.name
        new_data[f"{data.level.name.lower()}_id"] = data.id
        new_df = pd.DataFrame([new_data])
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_csv(filepath, index=False)
        return filepath
    else:
        logger.error(
            {
                "context": "insert_administration_row_csv",
                "message": (
                    f"{('test' if test else COUNTRY_NAME)}-administration.csv"
                    " doesn't exist"
                ),
            }
        )  # pragma: no cover
    return None


def find_index_by_id(df, id):
    for idx, row in df.iterrows():
        last_non_null_col = row.last_valid_index()
        last_non_null_value = row[last_non_null_col]
        if last_non_null_value == id:
            return idx
    return None


def administration_csv_update(data: dict):
    test = settings.TEST_ENV
    filename = "{0}-administration.csv".format(
        "test" if test else COUNTRY_NAME
    )
    filepath = f"{STORAGE_PATH}/master_data/{filename}"
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        index = find_index_by_id(df=df, id=data.pk)
        if index is not None:
            if data.path:
                parent_ids = list(
                    filter(lambda path: path, data.path.split("."))
                )
                parents = Administration.objects.filter(
                    pk__in=parent_ids, level__id__gt=1
                ).all()
                for p in parents:
                    df.loc[index, p.level.name.lower()] = p.name
                    df.loc[index, f"{p.level.name.lower()}_id"] = p.id
            df.loc[index, data.level.name.lower()] = data.name
            df.loc[index, f"{data.level.name.lower()}_id"] = data.id
        df.to_csv(filepath, index=False)
        return filepath
    else:
        logger.error(
            {
                "context": "update_administration_row_csv",
                "message": f"{filename} doesn't exist",
            }
        )  # pragma: no cover
    return None


def administration_csv_delete(id: int):
    test = settings.TEST_ENV
    filename = "{0}-administration.csv".format(
        "test" if test else COUNTRY_NAME
    )
    filepath = f"{STORAGE_PATH}/master_data/{filename}"
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        ix = find_index_by_id(df=df, id=id)
        if ix is not None:
            df.drop(index=ix, inplace=True)
        df.to_csv(filepath, index=False)
        return filepath
    else:
        logger.error(
            {
                "context": "delete_administration_row_csv",
                "message": f"{filename} doesn't exist",
            }
        )  # pragma: no cover
    return None
