import json

from django.core.management import BaseCommand
from jsmin import jsmin

from mis.settings import (
    APP_NAME,
    APP_SHORT_NAME,
    APK_NAME,
    SHOW_LANDING_PAGE,
)
from api.v1.v1_profile.models import Levels
from api.v1.v1_profile.constants import FeatureTypes, FeatureAccessTypes
from api.v1.v1_visualization.functions import refresh_materialized_data


class Command(BaseCommand):
    help = (
        "Generate source/config/config.min.js (levels, "
        "appConfig, roleFeatures) for the frontend bundle. "
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
        levels = []
        # NOTE: forms are no longer baked here. The web frontend fetches them
        # at runtime from GET /api/v1/forms/published so newly published forms
        # reflect without a config rebuild. See doc/claude/
        # remove-window-forms-runtime-fetch.md
        for level in Levels.objects.all():
            levels.append(
                {
                    "id": level.id,
                    "name": level.name,
                    "level": level.level,
                }
            )
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
                    "var levels=",
                    json.dumps(levels),
                    ";",
                    config_file,
                    "var appConfig=",
                    json.dumps({
                        "name": APP_NAME,
                        "shortName": APP_SHORT_NAME,
                        "apkName": APK_NAME,
                        "showLandingPage": SHOW_LANDING_PAGE,
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
        del levels
        del min_config
        if options.get("refresh_views"):
            refresh_materialized_data()
