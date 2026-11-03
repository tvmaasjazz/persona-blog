from decimal import Decimal

# The scale of every USD column (NUMERIC(16,10)); a charge is rounded to it so the step
# and its ledger row hold the same value
USD_QUANTUM = Decimal("1e-10")
