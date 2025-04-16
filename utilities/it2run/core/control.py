import logging
import sys
from .term import set_raw_mode, restore_mode
from .udsmux import UnixDomainSocketPair
from .io import io_loop

logger = logging.getLogger(__name__)

def connect(control_id, verbose=False):
    """
    Connect to an existing process using its control ID.
    
    Args:
        control_id (str): The ID of the process to connect to
        verbose (bool): Whether to enable verbose logging
    """
    logger.debug(f"Connecting to existing process with control ID: {control_id}")

    try:
        pair = UnixDomainSocketPair(id=control_id)
        pair.send(b"")
        logger.info(f"Connected to UDS pair with control ID: {control_id}")
        set_raw_mode()
        io_loop(sys.stdin.fileno(), sys.stdout.fileno(), pair)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")
        restore_mode()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to connect to UDS pair with control ID: {control_id}, error: {e}")
        restore_mode()
        sys.exit(1)