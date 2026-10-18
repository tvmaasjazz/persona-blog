# A step's output column is JSONB so a structured step can store more than prose later.
# Text steps put their text under this key.
STEP_OUTPUT_TEXT_KEY = "text"

# The Redis list a stopping process pushes a released run's id onto. Every deployed
# version must use the same key, or a handoff reaches no listener.
RUN_HANDOFF_QUEUE_KEY = "generate_text:run_handoff"

# Stored on a run picked up while still PENDING: its job never started, so
# there is no checkpoint to resume from.
RUN_NEVER_STARTED_ERROR_CODE = "RunNeverStarted"
RUN_NEVER_STARTED_ERROR_MESSAGE = "This run never started. Start it again."

# Stored on a run that was picked up more often than the settings allow.
RUN_PICKED_UP_TOO_OFTEN_ERROR_CODE = "RunPickedUpTooOften"
RUN_PICKED_UP_TOO_OFTEN_ERROR_MESSAGE = "This run kept being interrupted. Start it again."
