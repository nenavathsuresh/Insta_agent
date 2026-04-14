from loguru import logger

def setup_logger():
    logger.add("logs/app.log", rotation="5 MB", retention="10 days")
    return logger


logger = setup_logger()
