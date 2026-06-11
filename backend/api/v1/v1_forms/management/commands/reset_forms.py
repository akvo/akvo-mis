from django.core.management import call_command
from django.core.management import BaseCommand
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import SystemUser


class Command(BaseCommand):
    help = (
        "Reset all forms to their initial state by truncating and"
        "repopulating them."
    )
    # Add a test parameter to the command

    def add_arguments(self, parser):
        parser.add_argument(
            "--test",
            nargs="?",
            const=1,
            default=False,
            type=int
        )

    def handle(self, *args, **options):
        # Get all non-test users
        users = SystemUser.objects.exclude(
            email__contains="@test.com"
        ).all()
        user_forms = {}
        mobile_forms = {}
        for user in users:
            user_forms[user.id] = [
                uf.form for uf in user.user_form.all()
            ]
            for mobile_assignment in user.mobile_assignments.all():
                mobile_forms[mobile_assignment.id] = [
                    form for form in mobile_assignment.forms.all()
                ]
        # truncate all forms and related data. Forms is soft-deletable
        # (FB-004), so use hard_delete() to actually remove the rows —
        # a plain delete() would only set deleted_at and re-seeding would
        # then collide on the primary key.
        forms = Forms.objects.all()
        for form in forms:
            form.hard_delete()
        # Call form_seeder command to repopulate the forms
        test = options.get("test", False)
        if test:
            call_command(
                "form_seeder",
                "--test",
                stdout=self.stdout,
                stderr=self.stderr,
            )
        else:
            call_command(
                "form_seeder",
                stdout=self.stdout,
                stderr=self.stderr,
            )
        # Reset user form assignments
        test_users = SystemUser.objects.filter(
            email__contains="@test.com"
        ).all()
        for user in test_users:
            # delete all mobile assignments for test users
            user.mobile_assignments.all().delete()
            # delete all user forms for test users
            user.delete(hard=True)

        # Re-assign forms to users
        for user in SystemUser.objects.all():
            # restore the user's forms
            if user.id in user_forms:
                # filter Forms that were assigned to the user
                forms = Forms.objects.filter(
                    id__in=[uf.id for uf in user_forms[user.id]]
                ).all()
                for form in forms:
                    user.user_form.create(
                        form=form,
                    )
            # restore the mobile assignments
            for mobile_assignment in user.mobile_assignments.all():
                if mobile_assignment.id in mobile_forms:
                    # filter Forms that were assigned to the mobile assignment
                    forms = Forms.objects.filter(
                        id__in=[
                            f.id for f in mobile_forms[mobile_assignment.id]
                        ]
                    ).all()
                    for form in forms:
                        mobile_assignment.forms.add(form)
                # save the mobile assignment
                mobile_assignment.save()
        # Output success message
        self.stdout.write(self.style.SUCCESS("Successfully reset all forms."))
