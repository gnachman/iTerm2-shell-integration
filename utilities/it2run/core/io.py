#!/usr/bin/env python3
import logging
import os
import sys
import select
import fcntl

from .udsmux import UnixDomainSocketPair

MAX_BUFFER_SIZE = 65536  # maximum bytes to buffer before pausing reads

logger = logging.getLogger(__name__)

def set_nonblocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def io_loop(read_fd, write_fd, pair: UnixDomainSocketPair):
    """
    Forwards data bidirectionally between read_fd/write_fd and the
    Unix domain socket pair, using internal buffers limited to MAX_BUFFER_SIZE.
    
    Data read from read_fd is buffered to be sent over the socket using
    pair.send() with destination pair.reader_path, and data read
    from pair.receive() is buffered for writing to write_fd.
    
    Nonblocking I/O is used throughout and partial writes are handled.
    """
    # Get file descriptors for the pair's reader and writer sockets.
    pair_reader_fd = pair.fileno()
    pair_writer_fd = pair.fileno()
    logger.debug(f"io_loop with read_fd={read_fd}, write_fd={write_fd} pair_fd={pair.fileno()} server_path={pair.server_path} client_path={pair.client_path}")

    # Set nonblocking mode on both fds and socket endpoints
    set_nonblocking(read_fd)
    set_nonblocking(write_fd)
    set_nonblocking(pair_reader_fd)
    set_nonblocking(pair_writer_fd)

    buf_to_socket = bytearray()  # Data from read_fd to be sent via the UDS
    buf_to_fd = bytearray()      # Data from UDS to be written to write_fd
    eof_read = False             # read_fd EOF flag

    while True:
        rlist = []
        wlist = []

        logger.debug(f"eof_read={eof_read} len(buf_to_socket)={len(buf_to_socket)} len(buf_to_fd)={len(buf_to_fd)} connected={pair.connected()}")

        # Add read_fd for reading if not at EOF and the buffer isn't too full
        if not eof_read and len(buf_to_socket) < MAX_BUFFER_SIZE:
            rlist.append(read_fd)
        # Add the pair reader for reading if we haven't already filled buf_to_fd
        if len(buf_to_fd) < MAX_BUFFER_SIZE:
            rlist.append(pair_reader_fd)

        # Add write_fd for writing if there's data from the UDS to deliver
        if buf_to_fd:
            wlist.append(write_fd)
        # Add the pair writer for writing if there's data to send from read_fd
        if pair.connected() and buf_to_socket:
            wlist.append(pair_writer_fd)

        # If there's nothing pending, break out.
        if not rlist and not wlist:
            break

        logger.debug(f"Will call select with rlist={rlist} and wlist={wlist}. pair.connected()={pair.connected()}")
        ready_to_read, ready_to_write, _ = select.select(rlist, wlist, [])
        logger.debug(f"ready_to_read={ready_to_read} ready_to_write={ready_to_write}")

        # Read from the PTY master.
        if read_fd in ready_to_read:
            logger.debug(f"Reading from read_fd")
            try:
                data = os.read(read_fd, 1024)
                if data:
                    logger.debug(f"Read {len(data)} bytes from read_fd: {data.decode('utf-8')}")
                    buf_to_socket.extend(data)
                else:
                    logger.debug(f"EOF on read_fd")
                    eof_read = True
            except OSError:
                logger.debug("OSError while reading from read_fd")
                eof_read = True

        # Read from the Unix domain socket pair's reader.
        if pair_reader_fd in ready_to_read:
            logger.debug(f"Reading from UDS")
            try:
                # receive() returns a tuple (writer_id, message_id, message)
                msg = pair.receive()
                if msg is not None:
                    _, _, message = msg
                    buf_to_fd.extend(message)
                    logger.debug(f"Received message from UDS: {message.decode('utf-8') }")
            except Exception as e:
                logger.error(f"Error receiving message from UDS: {e}")
                # If receive() fails, just ignore and continue.
                pass

        # Write buffered data to the PTY master.
        if write_fd in ready_to_write and buf_to_fd:
            logger.debug(f"Writing {len(buf_to_fd)} bytes to write_fd: {buf_to_fd.decode('utf-8')}")
            try:
                n = os.write(write_fd, buf_to_fd)
                buf_to_fd = buf_to_fd[n:]
            except OSError as e:
                logger.error(f"OSError while writing to write_fd: {e}")
                pass

        # Write buffered data to the Unix domain socket via its writer.
        if pair_writer_fd in ready_to_write and buf_to_socket:
            logger.debug(f"Writing {len(buf_to_socket)} bytes to UDS: {buf_to_socket.decode('utf-8')}")
            try:
                # Send a chunk (up to 1024 bytes) from the buffer.
                chunk = bytes(buf_to_socket[:1024])
                logger.debug(f"Sending message to UDS: {chunk.decode('utf-8')}")
                sent = pair.send(chunk)
                if not pair.connected() and not pair.is_server:
                    logger.info("Sending failed in client so exiting")
                    return
                buf_to_socket = buf_to_socket[sent:]
            except Exception as e:
                logger.error(f"Error sending message to UDS: {e}")
                # If sending would block or another error occurs, simply continue.
                pass

        # Terminate if read_fd has reached EOF and both buffers are drained
        if eof_read and not buf_to_socket and not buf_to_fd:
            logger.debug(f"Terminating")
            break


