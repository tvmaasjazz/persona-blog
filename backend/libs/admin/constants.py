from decimal import Decimal

# The most one grant may give, so a typo like 1000 for 10 is refused
MAX_CREDIT_GRANT_USD = Decimal(100)
