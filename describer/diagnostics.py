"""Application diagnostics kept separate from third-party HTTP logging."""
import logging
from logging.handlers import RotatingFileHandler

def make_logger(settings):
    logger=logging.getLogger('DescriberWorkbench.'+str(id(settings)));logger.setLevel(logging.DEBUG);logger.propagate=False
    try:
        settings.path.parent.mkdir(parents=True,exist_ok=True)
        handler=RotatingFileHandler(settings.path.parent/'workbench.log',maxBytes=1024*1024,backupCount=1,encoding='utf8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logger.addHandler(handler)
    except OSError:pass # Status remains visible if the diagnostics folder is unwritable.
    return logger
