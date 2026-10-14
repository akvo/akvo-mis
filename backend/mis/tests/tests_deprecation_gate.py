import warnings

from django.test import SimpleTestCase
from django.utils.deprecation import RemovedInNextVersionWarning


class DeprecationGateTest(SimpleTestCase):
    # The gate exists so the next Django upgrade has no surprises: any
    # deprecated API this suite touches must fail here, on the version
    # that still offers the replacement, not after the upgrade removes it.

    def test_a_django_deprecation_fails_the_test(self):
        with self.assertRaises(RemovedInNextVersionWarning):
            warnings.warn("gate check", RemovedInNextVersionWarning)

    def test_other_deprecations_stay_warnings(self):
        # Third-party libraries deprecate things on their own schedule;
        # only Django's are gated, or one library would block a step.
        warnings.warn("not gated", DeprecationWarning)

    def test_a_future_warning_from_our_code_fails_the_test(self):
        # pandas announces its removals as FutureWarning attributed to
        # the caller, so this is how pandas 2 breakage shows up early.
        with self.assertRaises(FutureWarning):
            warnings.warn("gate check", FutureWarning)
