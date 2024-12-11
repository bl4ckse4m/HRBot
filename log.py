import logging

import colorlog

# Create a logger
def setup_logger():
    logger = colorlog.getLogger()

    # Set the log level
    logger.setLevel(logging.INFO)

    # Define a formatter with colors
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)s:%(name)s:%(message)s"
    )

    # Create a stream handler with the formatter
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)