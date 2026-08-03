import json

from django.core.management import BaseCommand
from jsmin import jsmin

from mis.settings import (
    APP_NAME,
    APP_SHORT_NAME,
    APK_NAME,
    BASE_DOMAIN,
    SHOW_LANDING_PAGE,
)
from api.v1.v1_profile.constants import FeatureTypes, FeatureAccessTypes
from api.v1.v1_visualization.functions import refresh_materialized_data


class Command(BaseCommand):
    help = (
        "Generate source/config/config.min.js (appConfig, "
        "roleFeatures) for the frontend bundle. "
        "Pass --refresh-views to also refresh the view_data_options "
        "materialized view (acquires an exclusive lock — see flag help)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh-views",
            action="store_true",
            help=(
                "Also REFRESH MATERIALIZED VIEW view_data_options after "
                "writing the config. WARNING: this takes an exclusive "
                "ACCESS EXCLUSIVE lock on the view and blocks readers "
                "and writers for the full refresh duration. CONCURRENTLY "
                "is not used because refresh_materialized_data() runs "
                "inside @transaction.atomic. Skip in routine config "
                "rebuilds (startup, missing-file regenerate); prefer "
                "the v1_data.tasks.refresh_materialized_data task or a "
                "maintenance window for explicit refreshes."
            ),
            default=False,
        )

    def handle(self, *args, **options):
        print("GENERATING CONFIG JS")

        # write config
        config_file = jsmin(open("source/config/config.js").read())
        # NOTE: neither forms nor levels are baked here any more. The web
        # frontend fetches both at runtime — forms from
        # GET /api/v1/forms/published, levels from GET /api/v1/levels —
        # because levels are tenant-owned and a global bake would show
        # every tenant's tiers to everyone.
        role_features = []
        for key, value in FeatureTypes.FieldStr.items():
            role_features.append(
                {
                    "id": key,
                    "name": value,
                    "access": [
                        {
                            "id": access_id,
                            "name": FeatureAccessTypes.FieldStr[access_id],
                        }
                        for access_id in FeatureTypes.FieldGroup[key]
                    ],
                }
            )
        min_config = jsmin(
            "".join(
                [
                    config_file,
                    "var appConfig=",
                    json.dumps({
                        "name": APP_NAME,
                        "shortName": APP_SHORT_NAME,
                        "apkName": APK_NAME,
                        "showLandingPage": SHOW_LANDING_PAGE,
                        # Empty on a single-host deployment, which is how
                        # the frontend knows not to split itself into
                        # base-domain and workspace contexts at all.
                        # tenant-info answers 204 in both cases, so the
                        # app cannot tell them apart without this.
                        "baseDomain": BASE_DOMAIN,
                    }),
                    ";",
                    "var roleFeatures=",
                    json.dumps(role_features),
                    ";",
                ]
            )
        )
        open("source/config/config.min.js", "w").write(min_config)
        # os.remove(administration_json)
        del min_config
        if options.get("refresh_views"):
            refresh_materialized_data()
