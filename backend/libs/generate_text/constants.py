# A step's output column is JSONB so a structured step can store more than prose later.
# Text steps put their text under this key.
STEP_OUTPUT_TEXT_KEY = "text"

# Stored on a run cancelled because the process stopped before it finished.
SERVER_SHUTDOWN_ERROR_CODE = "ServerShutdown"
SERVER_SHUTDOWN_ERROR_MESSAGE = "The server stopped before this run finished. Start it again."
