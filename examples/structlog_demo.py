"""Minimal structlog example.

This script demonstrates how to configure structlog to output JSON
formatted logs and how to log a simple message with context.
"""

import structlog

# Configure structlog to use the standard library logging module
# and render logs as JSON.
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Get a logger instance.
log = structlog.get_logger()

# Log a simple message with some context.
log.info("hello", user="alice", action="demo")

if __name__ == "__main__":
    # Running the script will produce a single JSON log line.
    pass
