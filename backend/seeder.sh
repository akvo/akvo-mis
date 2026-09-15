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
    python manage.py form_seeder || { echo "Form seeding failed — aborting."; exit 1; }
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
    read -r draft_data_input
    if [[ "${draft_data_input}" == 'y' || "${draft_data_input}" == 'Y' ]]; then
        draft_data=true
    else
        draft_data=false
    fi
        
    python manage.py default_roles_seeder
    python manage.py fake_complete_data_seeder --repeat="${fake_data_count}" --monitoring="${monitoring_data_count}" --approved="${approved}" --draft="${draft_data}"
fi

python manage.py generate_sqlite
python manage.py generate_config
