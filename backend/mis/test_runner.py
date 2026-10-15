import unittest

from django.test.runner import DiscoverRunner


class _GateTextTestRunner(unittest.TextTestRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Without -W on the command line, unittest sets this to
        # "default" and applies it over every filter for the run, which
        # would quietly disarm the deprecation gate in settings.
        self.warnings = None


class DeprecationGateRunner(DiscoverRunner):
    test_runner = _GateTextTestRunner
