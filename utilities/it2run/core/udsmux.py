import logging
import os
import socket
import struct
import math
import random

logger = logging.getLogger(__name__)

class UnixDomainSocketMux:
    HEADER_FORMAT = "!IIHH"  # writer_id, message_id, total_segments, segment_index
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_DATAGRAM_SIZE = 1024
    MAX_PAYLOAD_SIZE = MAX_DATAGRAM_SIZE - HEADER_SIZE

    def __init__(self, socket_path, peer_path=None, server=True):
        """
        Initialize a Unix domain socket multiplexer.
        
        Args:
            socket_path: Path to bind this socket to (required for both server and client)
            peer_path: Path to the peer's socket (required for communication)
            server: Whether this is in server mode (True) or client mode (False)
        """
        self.server = server
        self.socket_path = os.path.expanduser(socket_path) if socket_path else None
        self.peer_path = os.path.expanduser(peer_path) if peer_path else None
        
        # Create socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        
        # Both server and client need to bind to their own socket_path
        if not self.socket_path:
            raise ValueError("Both server and client mode require a socket_path to bind to")
            
        # Create directory if needed
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        
        # Clean up any existing socket file
        if os.path.exists(self.socket_path):
            logger.debug(f"unlink {self.socket_path}")
            os.unlink(self.socket_path)
            
        # Bind socket
        logger.debug(f"bind {self.socket_path}")
        self.sock.bind(self.socket_path)
        
        # Set permissions (only for server mode)
        if self.server:
            os.chmod(self.socket_path, 0o600)
            
        # For sending messages, peer_path is required
        if not self.peer_path and not self.server:
            raise ValueError("Client mode requires a peer_path")
        
        self.sock.setblocking(False)
        self.framer = _MessageFramer()
        self.writer_id = os.getpid()
        self._message_counter = 0
        self.verbose = False
        self.connected = False

    def send(self, message: bytes):
        """
        Send a message to the peer.
        
        In server mode with no peer_path, this will raise an exception.
        
        Returns:
            int: Number of bytes sent successfully
        """
        if not self.peer_path:
            raise ValueError("Cannot send without a peer_path")
            
        self._message_counter += 1
        message_id = self._message_counter
        total_segments = math.ceil(len(message) / self.MAX_PAYLOAD_SIZE) or 1
        
        logger.debug(f"Sending message {message_id} in {total_segments} segments to {self.peer_path}")
        
        bytes_sent = 0
        for seg_index in range(total_segments):
            start = seg_index * self.MAX_PAYLOAD_SIZE
            segment = message[start:start+self.MAX_PAYLOAD_SIZE]
            header = struct.pack(self.HEADER_FORMAT,
                                 self.writer_id, message_id,
                                 total_segments, seg_index)
            logger.debug(f"Sending segment {seg_index+1}/{total_segments} on fd {self.sock.fileno()}")
            
            try:
                sent = self.sock.sendto(header + segment, self.peer_path)
                bytes_sent += sent - self.HEADER_SIZE  # Don't count header bytes in return value
            except ConnectionRefusedError:
                logger.debug("Connection refused - peer has disconnected")
                self.connected = False
                return bytes_sent
            
        return bytes_sent

    def receive(self):
        """
        Receive a message from the peer.
        
        Returns:
            A tuple (writer_id, message_id, message) if a complete message is available,
            or None if no data is available or the message is incomplete.
        """
        try:
            logger.debug(f"Receiving message on {self.socket_path or 'client socket'}")
            data, addr = self.sock.recvfrom(self.MAX_DATAGRAM_SIZE)
            self.connected = True
            logger.debug(f"Received message from addr={addr}")
            
            # Note: For Unix domain sockets, addr might be an empty string 
            # if the sender didn't bind to a path
            # We'll rely on the peer_path being set explicitly rather than from addr
                
        except BlockingIOError as e:
            logger.error(f"BlockingIOError: {e}")
            return None
            
        if len(data) < self.HEADER_SIZE:
            logger.error(f"Short datagram: {len(data)} < {self.HEADER_SIZE}")
            return None  # Malformed datagram.
            
        header = struct.unpack(self.HEADER_FORMAT, data[:self.HEADER_SIZE])
        payload = data[self.HEADER_SIZE:]
        logger.debug(f"Received message {header[1]} from {header[0]}")
        
        return self.framer.add_segment(header, payload)

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        self.sock.close()
        if self.socket_path and os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass


class _MessageFramer:
    def __init__(self):
        # Maps (writer_id, message_id) to a list of segments.
        self.messages = {}

    def add_segment(self, header, data):
        writer_id, message_id, total_segments, seg_index = header
        key = (writer_id, message_id)
        if key not in self.messages:
            self.messages[key] = [None] * total_segments
        self.messages[key][seg_index] = data
        if all(segment is not None for segment in self.messages[key]):
            complete_message = b"".join(self.messages[key])
            del self.messages[key]
            return writer_id, message_id, complete_message
        return None


class UnixDomainSocketPair:
    def __init__(self, base_dir="~/.iterm2", id=None):
        """
        Create a pair of Unix domain sockets for bidirectional communication.
        
        Args:
            base_dir: Base directory for socket files
            id: If provided, acts as client connecting to an existing server with this ID.
                If None, acts as server and generates a new ID.
        """
        base_dir = os.path.expanduser(base_dir)
        
        if id is None:
            self.is_server = True
            # Server mode: generate an ID and bind
            self.id = f"{random.getrandbits(64):016x}"
            server_path = os.path.join(base_dir, f"server-{self.id}")
            client_path = os.path.join(base_dir, f"client-{self.id}")
            
            logger.debug(f"Server mode: id={self.id}")
            
            # Server binds to server_path, knows client will be at client_path
            self.socket_mux = UnixDomainSocketMux(server_path, peer_path=client_path, server=True)
            
            # Connection info to share with clients
            self.connection_info = {"id": self.id, "server_path": server_path, "client_path": client_path}

        else:
            # Client mode: use provided id to connect to server
            self.id = id
            self.is_server = False
            server_path = os.path.join(base_dir, f"server-{self.id}")
            client_path = os.path.join(base_dir, f"client-{self.id}")
            
            logger.debug(f"Client mode: id={self.id}")
            
            # Client binds to client_path and knows server_path
            self.socket_mux = UnixDomainSocketMux(client_path, peer_path=server_path, server=False)
        self.server_path = server_path
        self.client_path = client_path
            
    def send(self, message):
        """
        Send a message to the peer
        
        Returns:
            bool: True if message was sent successfully, False if connection refused
        """
        return self.socket_mux.send(message)
        
    def receive(self):
        """Receive a message from the peer"""
        return self.socket_mux.receive()
        
    def fileno(self):
        """Return the file descriptor for polling"""
        return self.socket_mux.fileno()

    def close(self):
        """Close the socket pair and clean up"""
        try:
            self.socket_mux.close()
        except Exception:
            pass

    def connected(self):
        return self.socket_mux.connected
