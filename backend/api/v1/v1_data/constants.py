"""Markers for seeder-generated data (SEED-001).

Anything carrying DUMMY_PREFIX is fair game for
`fake_complete_data_seeder --clean`, which hard-deletes it. Never apply
the prefix to a row a human might have authored.
"""

DUMMY_PREFIX = "DUMMY-"

# Seeded accounts are additionally namespaced by email so --clean can find
# them without depending on first/last name, which Faker randomises.
DUMMY_EMAIL_PREFIX = "dummy-"
DUMMY_EMAIL_DOMAIN = "@test.com"
