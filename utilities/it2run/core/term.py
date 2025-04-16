import os
import base64
import fcntl
import logging
import struct
import sys
import termios

logger = logging.getLogger(__name__)

_original_term_settings = None

def encode_to_base64(s: str) -> str:
    b = s.encode("utf-8")
    encoded_bytes = base64.b64encode(b)
    return encoded_bytes.decode("ascii")

def make_osc_sequence(number: int, payload: str, verbose: bool) -> str:
    """
    Build an OSC control sequence with the given payload.
    If $TERM contains "screen", wrap it with tmux's DCS escaping.

    The OSC sequence is formed as:
        ESC ] payload BEL

    And if $TERM indicates tmux (typically "screen*"),
    it is wrapped as:
        ESC P tmux; <ESC-escaped OSC sequence> ESC \
    """
    if verbose:
        logger.debug(f"Making OSC sequence {number};{payload}")

    # Build standard OSC sequence.
    osc_seq = "\033]" + str(number) + ";" + payload + "\007"

    # Check if $TERM contains "screen" (case-insensitive).
    if "screen" in os.environ.get("TERM", "").lower():
        # Escape every ESC in the OSC sequence by doubling them.
        escaped_seq = osc_seq.replace("\033", "\033\033")
        # Wrap using tmux's DCS escaping.
        osc_seq = "\033Ptmux;" + escaped_seq + "\033\\"

    return osc_seq

def start(cmd, uid, verbose):
    b64cmd = encode_to_base64(cmd)
    sys.stdout.write(make_osc_sequence(1337, f"wrap=a=start;cmd={b64cmd};uid={uid}", verbose))
    sys.stdout.flush()

def update_pty_size(fd):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    winsize = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

def set_cbreak_mode():
    """Put terminal into cbreak mode (no echo, but signals enabled), saving original settings"""
    global _original_term_settings
    fd = sys.stdin.fileno()
    _original_term_settings = termios.tcgetattr(fd)
    
    # Get current settings and modify for cbreak mode
    cbreak = termios.tcgetattr(fd)
    cbreak[3] &= ~(termios.ECHO | termios.ICANON)  # Disable ECHO and canonical mode
    # Note: We don't disable ISIG, so ^C (SIGINT) still works
    
    # Set new terminal settings
    termios.tcsetattr(fd, termios.TCSANOW, cbreak)

def restore_mode():
    """Restore terminal to original settings"""
    global _original_term_settings
    if _original_term_settings is not None:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, _original_term_settings)

def set_raw_mode():
    """Put terminal into raw mode (no echo, no signals, no processing), saving original settings"""
    global _original_term_settings
    fd = sys.stdin.fileno()
    _original_term_settings = termios.tcgetattr(fd)
    
    # Get current settings and modify for raw mode
    raw = termios.tcgetattr(fd)
    raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)  # Input flags
    raw[1] &= ~(termios.OPOST)  # Output flags
    raw[2] &= ~(termios.CSIZE | termios.PARENB)  # Control flags
    raw[2] |= termios.CS8
    raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)  # Local flags
    
    # Set new terminal settings
    termios.tcsetattr(fd, termios.TCSANOW, raw)

