"""The approved security values (decision 0003). Change only with a recorded decision."""

from datetime import timedelta

from common.security import Limit

# 3.1 Staff sessions
STAFF_IDLE_TIMEOUT = timedelta(minutes=30)
STAFF_ABSOLUTE_LIFETIME = timedelta(hours=12)

# 3.2 Customer sessions
CUSTOMER_BROWSER_SESSION_CAP = timedelta(hours=24)
CUSTOMER_REMEMBER_IDLE = timedelta(days=30)
CUSTOMER_REMEMBER_ABSOLUTE = timedelta(days=90)

# 2.5 Re-confirmation of the second factor
STEP_UP_VALIDITY = timedelta(minutes=5)

# 2.3 Recovery codes
RECOVERY_CODE_COUNT = 10

# 3.4 / 2.4 Staff lockout: 5 failures (password or code) in 15 minutes lock for 15 minutes
STAFF_FAILURE_LIMIT = Limit(count=5, window=15 * 60)
STAFF_LOCK_SECONDS = 15 * 60

# 3.4 Per-network-address limits. The decision fixes the rule; these numbers are implementation defaults.
STAFF_AUTH_PER_IP = Limit(count=30, window=15 * 60)
CUSTOMER_AUTH_PER_IP = Limit(count=60, window=15 * 60)
LINK_REQUESTS_PER_IP = Limit(count=10, window=60 * 60)  # password-reset and similar email requests
LINK_REQUESTS_PER_EMAIL = Limit(count=3, window=60 * 60)

# 3.4 Customers: growing delays after 5 failures, no hard lockout
CUSTOMER_FREE_FAILURES = 5
CUSTOMER_FAILURE_WINDOW = Limit(count=10_000, window=60 * 60)
CUSTOMER_MAX_DELAY_SECONDS = 15 * 60

# 3.5 Passwords
STAFF_PASSWORD_MIN = 12
CUSTOMER_PASSWORD_MIN = 10
PASSWORD_MAX = 128

# 3.6 Single-use links
STAFF_INVITE_LIFETIME = timedelta(hours=48)
PASSWORD_RESET_LIFETIME = timedelta(minutes=30)
RECOVERY_LINK_LIFETIME = timedelta(minutes=30)
# Implementation default (not a decision item): customer email-verification links.
CUSTOMER_VERIFY_LIFETIME = timedelta(hours=24)

# 4.3 Owner recovery by another Owner waits 24 hours; the cancellation link lasts the whole wait.
OWNER_RECOVERY_WAIT = timedelta(hours=24)

# The pending second-factor step of a staff sign-in.
MFA_CHALLENGE_SECONDS = 5 * 60
