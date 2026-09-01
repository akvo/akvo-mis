#!/usr/bin/env bash
#
# One seeder for every environment.
#
# seeder.prod.sh used to be a near-copy of this file and had drifted in
# both directions: it alone seeded entities, and it alone lacked the
# form_seeder abort and the cache clear. Nothing invoked it -- no CI job,
# no Dockerfile, no documentation -- so the two were merged here rather
# than kept in sync by hand.
#
# The workspace is an argument, not a prompt. Every tenant-aware command
# below needs the same value, and asking for it three times invites three
# different answers.

usage() {
    cat <<'EOF'
Usage: ./seeder.sh --tenant=<subdomain>

  --tenant=<subdomain>  Workspace the forms and generated data belong to.
                        'default' exists on any migrated database.
  -h, --help            Show this message.

Administrations, organisations, entities, attributes and roles are not
workspace-scoped and ignore this value.
EOF
}

tenant=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tenant=*) tenant="${1#*=}" ;;
        --tenant)   shift; tenant="${1:-}" ;;
        -h|--help)  usage; exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2
            echo >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if [[ -z "${tenant}" ]]; then
    echo "--tenant is required." >&2
    echo >&2
    usage >&2
    exit 1
fi

echo "Seeding into workspace: ${tenant}"
echo

echo "Seed Administration? [y/n]"
read -r seed_administration
if [[ "${seed_administration}" == 'y' || "${seed_administration}" == 'Y' ]]; then
    python manage.py administration_seeder
    python manage.py resetsequence v1_profile
fi

echo "Seed Form? [y/n]"
read -r seed_form
if [[ "${seed_form}" == 'y' || "${seed_form}" == 'Y' ]]; then
    python manage.py form_seeder --tenant="${tenant}" \
        || { echo "Form seeding failed — aborting."; exit 1; }
    python manage.py generate_config
    python manage.py clear_cache
fi

echo "Add New Super Admin? [y/n]"
read -r add_account
if [[ "${add_account}" == 'y' || "${add_account}" == 'Y' ]]; then
    echo "Please type email address"
    read -r email_address
    if [[ "${email_address}" != '' ]]; then
        python manage.py createsuperuser --email "${email_address}"
        python manage.py assign_forms "${email_address}"
    fi
fi

echo "Seed Organisation? [y/n]"
read -r seed_organization
if [[ "${seed_organization}" == 'y' || "${seed_organization}" == 'Y' ]]; then
    python manage.py organisation_seeder
fi

echo "Seed Entities? [y/n]"
read -r seed_entities
if [[ "${seed_entities}" == 'y' || "${seed_entities}" == 'Y' ]]; then
    python manage.py entities_seeder
fi

echo "Seed Administration Attribute? [y/n]"
read -r seed_administration_attribute
if [[ "${seed_administration_attribute}" == 'y' \
      || "${seed_administration_attribute}" == 'Y' ]]; then
    python manage.py administration_attribute_seeder
fi

# Roles are defined per level, so this has to follow the administration
# step rather than lead it. It is idempotent, and the fake data below
# cannot run without a role granting submit access.
echo "Seed Default Roles? [y/n]"
echo "  One Admin / Submitter / Approver role per administration level."
read -r seed_roles
if [[ "${seed_roles}" == 'y' || "${seed_roles}" == 'Y' ]]; then
    python manage.py default_roles_seeder
fi

# settings.py reads DEBUG by presence, not value:
#   DEBUG = True if "DEBUG" in environ else False
# Mirrored here so this prompt appears exactly where the seeder's own
# --clean guard would allow the data to be removed again. Offering to
# generate fake data that cannot then be cleaned is worse than not
# offering at all.
if [[ -z "${DEBUG+x}" ]]; then
    echo "Skipping fake data: DEBUG is not set, so this is not a"
    echo "development environment and --clean would refuse to undo it."
else
    echo "Seed Fake Data? [y/n]"
    read -r fake_data
    if [[ "${fake_data}" == 'y' || "${fake_data}" == 'Y' ]]; then
        echo "How many fake data do you want to create? (default is 5)"
        read -r fake_data_count
        if [[ "${fake_data_count}" == '' ]]; then
            fake_data_count=5
        fi
        echo "How many monitoring data do you want to create? (default is 2)"
        read -r monitoring_data_count
        if [[ "${monitoring_data_count}" == '' ]]; then
            monitoring_data_count=2
        fi

        # Both extras default to "no". Pending and draft submissions are
        # invisible in Manage Data, so a run that accepts the defaults
        # must produce data the operator can actually see — otherwise a
        # seeded environment looks broken.
        echo "Also create pending (unapproved) data? [y/N]"
        echo "  Needed only to exercise the approval workflow."
        read -r pending_data
        if [[ "${pending_data}" == 'y' || "${pending_data}" == 'Y' ]]; then
            # --approved=false is what makes the seeder mark data pending.
            approved=false
        else
            approved=true
        fi

        echo "Also create draft data? [y/N]"
        echo "  Drafts appear only under Manage Drafts, for their creator."
        echo "  Requires pending data: approved submissions have no drafts."
        read -r draft_data_input
        if [[ "${draft_data_input}" == 'y' \
              || "${draft_data_input}" == 'Y' ]]; then
            draft_data=true
            # --approved=true and --draft=true contradict each other and
            # the seeder rejects the pair outright.
            approved=false
        else
            draft_data=false
        fi

        # Required, with no default: every workspace is a different
        # country, and a silent default puts every generated pin in the
        # wrong place.
        echo "Bounding box for generated map points?"
        echo "  Format: minLng,minLat,maxLng,maxLat"
        echo "  Fiji:      177.0,-18.3,180.0,-16.1"
        echo "  Indonesia: 95.0,-11.0,141.0,6.0"
        read -r bbox
        while [[ "${bbox}" == '' ]]; do
            echo "A bounding box is required. Please enter one:"
            read -r bbox
        done

        python manage.py fake_complete_data_seeder \
            --tenant="${tenant}" \
            --bbox="${bbox}" \
            --repeat="${fake_data_count}" \
            --monitoring="${monitoring_data_count}" \
            --approved="${approved}" \
            --draft="${draft_data}"
    fi
fi

python manage.py generate_sqlite
python manage.py generate_config
