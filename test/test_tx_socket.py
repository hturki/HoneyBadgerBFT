import rlp
import socket
from honeybadgerbft.core.tx_socket import bind_codec_socket

def test_rlp_round_trip():
    server_path = "/tmp/rlp-test-server"
    rlp_sock = bind_codec_socket(server_path, rlp.encode, rlp.decode)
    txes = ["x", "y", "z"]

    raw_client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    raw_client.bind("/tmp/rlp-test-client")
    raw_client.connect(server_path)
    raw_client.send(rlp.encode(txes))

    assert rlp_sock.read() == txes
