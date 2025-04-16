import udsmux
import logging
import sys

logging.disable(logging.NOTSET)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

server=udsmux.UnixDomainSocketPair("/tmp")
client=udsmux.UnixDomainSocketPair("/tmp", server.id)
client.send(b'hello')
server.receive()
