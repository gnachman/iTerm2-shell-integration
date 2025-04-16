from .io import io_loop
from .term import start, update_pty_size, set_cbreak_mode, restore_mode
from .udsmux import UnixDomainSocketPair
import logging
import os
import pty
import signal
import sys
import time
import fcntl

logger = logging.getLogger(__name__)

VERBOSE=False

def run_child(exe, cmd, write_fd):
    """Runs after fork, on the child side."""
    if VERBOSE:
        logger.debug(f"Child pgid before setsid: {os.getpgrp()}")
    try:
        os.setsid()
    except PermissionError:
        # Process is already a process group leader
        if VERBOSE:
            logger.debug("Could not create new session (process is already a process group leader)")
    if VERBOSE:
        logger.debug(f"Child pgid after setsid: {os.getpgrp()}")

    # Close all FDs except stdin, stdout, stderr, and write_fd
    os.closerange(3, write_fd)
    os.closerange(write_fd + 1, os.sysconf("SC_OPEN_MAX"))

    try:
        os.execvp(exe, cmd)
    except OSError as e:
        sys.stderr.write(f"Execution failed: {e}\n")
        os.write(write_fd, f"{e}".encode())
        sys.exit(1)


def run_parent(master_fd, child_pid, cmd, read_fd):
    """Runs after fork, on the parent size."""
    # Check if child successfully exec'd
    os.set_blocking(read_fd, True)
    error = os.read(read_fd, 1024)
    os.close(read_fd)
    
    if error:
        error_msg = error.decode()
        logger.error(f"Child process failed to execute: {error_msg}")
        sys.exit(1)

    logger.info("Parent side of fork")
    logger.debug(f"Parent pgid: {os.getpgrp()}")
    logger.debug(f"Parent sid: {os.getsid(0)}")
    logger.debug(f"Child pid: {child_pid}")
    logger.debug(f"Is master_fd a TTY?: {os.isatty(master_fd)}")
    
    update_pty_size(master_fd)
    signal.signal(signal.SIGWINCH, lambda s, f: update_pty_size(master_fd))
    
    io_pid = None
    pair = UnixDomainSocketPair()
    if VERBOSE:
        print(pair.id)
    # Fork before io_loop
    try:
        io_pid = os.fork()
    except OSError as e:
        try:
            os.kill(child_pid, signal.SIGKILL)
        except OSError:
            pass
        sys.stderr.write(f"{os.path.basename(sys.argv[0])}: fork failed: {e.strerror}\n")
        sys.exit(1)
        
    if io_pid == 0:
        # Child process handles IO
        io_loop(master_fd, master_fd, pair)
        pair.close()
        _, status = os.waitpid(child_pid, 0)
        sys.exit(os.WEXITSTATUS(status))
    else:
        start(cmd, pair.id, VERBOSE)

def run(exe, cmd, verbose):
    global VERBOSE
    VERBOSE=verbose
    read_fd, write_fd = os.pipe()
    fcntl.fcntl(write_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
    try:
        pid, master_fd = pty.fork()
    except OSError as e:
        sys.stderr.write(f"{os.path.basename(sys.argv[0])}: fork failed: {e.strerror}\n")
        sys.exit(1)
    
    if pid == 0:
        os.close(read_fd)
        run_child(exe, cmd, write_fd)
    else:
        os.close(write_fd)
        try:
            run_parent(master_fd, pid, ' '.join(cmd), read_fd)
        except KeyboardInterrupt:
            sys.exit(1)
        except Exception as e:
            if VERBOSE:
                import traceback
                traceback.print_exc()
            else:
                sys.stderr.write(f"Error: {str(e)}\n")
            sys.exit(1)


