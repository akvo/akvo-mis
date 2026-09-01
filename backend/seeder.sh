#!/usr/bin/env bash

echo "Seed Administration? [y/n]"
read -r seed_administration
if [[ "${seed_administration}" == 'y' || "${seed_administration}" == 'Y' ]]; then
    python manage.py administration_seeder
    python manage.py resetsequence v1_profile
fi

echo "Seed Form? [y/n]"
read -r seed_form
if [[ "${seed_form}" == 'y' || "${seed_form}" == 'Y' ]]; then
    echo "Which workspace (subdomain) do these forms belong to?"
    echo "  Leave blank for a single-host install (no workspace)."
    read -r form_subdomain
    form_tenant_arg=()
    if [[ "${form_subdomain}" != '' ]]; then
        form_tenant_arg=(--tenant="${form_subdomain}")
    fi
    python manage.py form_seeder "${form_tenant_arg[@]}" || { echo "Form seeding failed — aborting."; exit 1; }
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

echo "Seed Administration Attribute? [y/n]"
read -r seed_administration_attribute
if [[ "${seed_administration_attribute}" == 'y' || "${seed_administration_attribute}" == 'Y' ]]; then
    python manage.py administration_attribute_seeder
fi

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
    # invisible in Manage Data, so a run that accepts the defaults must
    # produce data the operator can actually see — otherwise a seeded
    # environment looks broken.
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
    if [[ "${draft_data_input}" == 'y' || "${draft_data_input}" == 'Y' ]]; then
        draft_data=true
        # --approved=true and --draft=true contradict each other and the
        # seeder now rejects the pair outright.
        approved=false
    else
        draft_data=false
    fi

    # Required: a hierarchy belongs to a workspace, and an unscoped run
    # would seed into whichever tenant the planner happened to return.
    echo "Which workspace (subdomain) should the data belong to? [default]"
    read -r subdomain
    if [[ "${subdomain}" == '' ]]; then
        subdomain=default
    fi

    # Required, with no default: every workspace is a different country,
    # and a silent default puts every generated pin in the wrong place.
    echo "Bounding box for generated map points?"
    echo "  Format: minLng,minLat,maxLng,maxLat"
    echo "  Fiji:      177.0,-18.3,180.0,-16.1"
    echo "  Indonesia: 95.0,-11.0,141.0,6.0"
    read -r bbox
    while [[ "${bbox}" == '' ]]; do
        echo "A bounding box is required. Please enter one:"
        read -r bbox
    done

    python manage.py default_roles_seeder
    python manage.py fake_complete_data_seeder \
        --repeat="${fake_data_count}" \
        --monitoring="${monitoring_data_count}" \
        --approved="${approved}" \
        --draft="${draft_data}" \
        --tenant="${subdomain}" \
        --bbox="${bbox}"
fi

python manage.py generate_sqlite
python manage.py generate_config
