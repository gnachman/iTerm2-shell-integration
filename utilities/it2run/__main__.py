import os
import shutil
import sys
import argparse
import logging
from .core import connect, run

def setup_logging(verbose, control_mode):
    if verbose:
        logging.disable(logging.NOTSET)
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        filename = "control.log" if control_mode else "app.log"
        print(f'Logging to {filename} because control_mode is {control_mode}')
        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        # Disable all logging messages.
        logging.disable(logging.CRITICAL)

def parse_args():
    parser = argparse.ArgumentParser(usage="%(prog)s [-v] [-d] [--control ID) [command args...]")
    parser.add_argument("-d", "--daemon", action="store_true",
                        help="Run as a daemon")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose mode")
    parser.add_argument("--control", metavar="ID",
                        help="Connect to existing process with specified ID")
    
    # Make command and args optional
    parser.add_argument("command", nargs='?', help="The command to run")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="Arguments for the command")
    args = parser.parse_args()

    # Validate arguments
    if args.control:
        if args.command:
            parser.error("Command cannot be specified with --control")
        return None, None, args.verbose, args.control, args.daemon
    
    if not args.command:
        parser.error("Command is required when not using --control")

    exe = shutil.which(args.command)
    if exe is None:
        sys.stderr.write(f"Command not found: {args.command}\n")
        sys.exit(1)

    cmd = [exe] + args.args
    return exe, cmd, args.verbose, None, args.daemon

def main():
    exe, cmd, verbose, control_id, daemon = parse_args()
    setup_logging(verbose, control_id != None)
    logger = logging.getLogger(__name__)
    
    if control_id:
        logger.info(f'Connecting to existing process {control_id}')
        connect(control_id, verbose=verbose)
    else:
        logger.info(f'Run {cmd}')
        run(exe, cmd, verbose=verbose)

if __name__ == '__main__':
    main()
