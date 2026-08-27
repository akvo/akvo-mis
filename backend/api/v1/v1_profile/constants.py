from mis.settings import COUNTRY_NAME


class OrganisationTypes:
    member = 1
    partnership = 2

    FieldStr = {
        member: "member",
        partnership: "partnership",
    }


class EntityTypes:
    school = 1
    health_care_facility = 2
    water_treatment_plant = 3
    rural_water_supply = 4

    FieldStr = {
        school: "School",
        health_care_facility: "Health Care Facilities",
        water_treatment_plant: "Water Treatment Plant",
        rural_water_supply: "Rural Water Supply",
    }


class DataAccessTypes:
    read = 1
    approve = 2
    submit = 3
    edit = 4
    delete = 5

    FieldStr = {
        read: "Read",
        approve: "Approve",
        submit: "Submit",
        edit: "Edit",
        delete: "Delete",
    }


class FeatureAccessTypes:
    invite_user = 1
    form_view = 3
    form_create = 4
    form_edit = 5
    form_publish = 6
    form_delete = 7
    # Continue from 7 rather than filling the gap at 2: these values are
    # persisted in role_feature_access rows, so a reused number would
    # silently re-point existing grants.
    dashboard_view = 8
    dashboard_create = 9
    dashboard_edit = 10
    dashboard_publish = 11
    dashboard_delete = 12
    dashboard_share_public = 13

    FieldStr = {
        invite_user: "Invite User",
        form_view: "Form View",
        form_create: "Form Create",
        form_edit: "Form Edit",
        form_publish: "Form Publish",
        form_delete: "Form Delete",
        dashboard_view: "Dashboard View",
        dashboard_create: "Dashboard Create",
        dashboard_edit: "Dashboard Edit",
        dashboard_publish: "Dashboard Publish",
        dashboard_delete: "Dashboard Delete",
        dashboard_share_public: "Dashboard Share Publicly",
    }


class FeatureTypes:
    user_access = 1
    form_builder = 2
    dashboard_builder = 3
    FieldStr = {
        user_access: "User Access",
        form_builder: "Form Builder",
        dashboard_builder: "Dashboard Builder",
    }
    FieldGroup = {
        user_access: [
            FeatureAccessTypes.invite_user,
        ],
        form_builder: [
            FeatureAccessTypes.form_view,
            FeatureAccessTypes.form_create,
            FeatureAccessTypes.form_edit,
            FeatureAccessTypes.form_publish,
            FeatureAccessTypes.form_delete,
        ],
        # One entry is the whole role-editor integration: generate_config
        # walks FieldStr and emits each key's FieldGroup members.
        dashboard_builder: [
            FeatureAccessTypes.dashboard_view,
            FeatureAccessTypes.dashboard_create,
            FeatureAccessTypes.dashboard_edit,
            FeatureAccessTypes.dashboard_publish,
            FeatureAccessTypes.dashboard_delete,
            FeatureAccessTypes.dashboard_share_public,
        ],
    }


ADMINISTRATION_CSV_FILE = f"{COUNTRY_NAME}-administration.csv"

# This is the default administration data used for testing
# and seeding the database.
# It contains a list of dictionaries, each representing an administrative unit
# with its corresponding codes and names at various levels.

DEFAULT_ADMINISTRATION_DATA = [
    {
        "id": 111,
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-JK",
        "Province_1": "Jakarta",
        "code_2": "ID-JK-JKE",
        "District_2": "East Jakarta",
        "code_3": "ID-JK-JKE-KJ",
        "Subdistrict_3": "Kramat Jati",
        "code_4": "ID-JK-JKE-KJ-CW",
        "Village_4": "Cawang",
    },
    {
        "id": 222,
        "code_0": "ID",
        "National_0": "Indonesia",
        "code_1": "ID-YGK",
        "Province_1": "Yogyakarta",
        "code_2": "ID-YGK-SLE",
        "District_2": "Sleman",
        "code_3": "ID-YGK-SLE-SET",
        "Subdistrict_3": "Seturan",
        "code_4": "ID-YGK-SLE-SET-CEP",
        "Village_4": "Cepit Baru",
    },
]

DEFAULT_ADMINISTRATION_LEVELS = [
    {"id": 1, "level": 0, "name": "NAME_0", "alias": "National"},
    {"id": 2, "level": 1, "name": "NAME_1", "alias": "Province"},
    {"id": 3, "level": 2, "name": "NAME_2", "alias": "District"},
    {"id": 4, "level": 3, "name": "NAME_3", "alias": "Subdistrict"},
    {"id": 5, "level": 4, "name": "NAME_4", "alias": "Village"},
]

TEST_GEO_DATA = [
    {"name": "Cawang", "X": 106.8456, "Y": -6.2088},
    {"name": "Cepit Baru", "X": 110.4170, "Y": -7.7326},
    {"name": "Kramat Jati", "X": 106.8456, "Y": -6.2088},
    {"name": "Seturan", "X": 110.4170, "Y": -7.7326},
    {"name": "East Jakarta", "X": 106.8456, "Y": -6.2088},
    {"name": "Sleman", "X": 110.4170, "Y": -7.7326},
    {"name": "Jakarta", "X": 106.8456, "Y": -6.2088},
    {"name": "Yogyakarta", "X": 110.4170, "Y": -7.7326},
    {"name": "Indonesia", "X": 106.8456, "Y": -6.2088},
]
