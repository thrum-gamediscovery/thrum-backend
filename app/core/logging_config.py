"""
Configures logging across the application.

Logs INFO level messages with timestamp and log level.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
