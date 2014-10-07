import sys
import signal

#
# Uncaught exception hooks
#

def register_excepthook(func):
    except_hooks.append(func)

def run_excepthooks(exctype, value, traceback):
    for f in reversed(except_hooks):
        f(exctype, value, traceback)
    # interpreter will exit after this func returns

except_hooks = [sys.excepthook]
sys.excepthook = run_excepthooks

#
# Signal handlers
#

def register_sig_handler(func):
    sig_handlers.append(func)

def run_sig_handlers(signum, frame):
    for f in reversed(sig_handlers):
        f(signum, frame)
    sys.exit(10)

sig_handlers = []
signal.signal(signal.SIGTERM, run_sig_handlers)
signal.signal(signal.SIGINT, run_sig_handlers)
