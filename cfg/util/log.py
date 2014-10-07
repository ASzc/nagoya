import logging

logging.basicConfig(level=logging.INFO, format="%(module)s.%(funcName)s %(levelname)s: %(message)s")
log = logging.getLogger()
log.debug("Logging set up")
