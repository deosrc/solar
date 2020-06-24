"""Test cases for inverter.py."""
from io import BytesIO
from queue import Queue
from socket import socketpair, create_connection
from threading import Thread
from time import sleep
from unittest import TestCase

from samil.inverter import calculate_checksum, construct_message, Inverter, InverterEOFError, InverterFinder, \
    InverterNotFoundError, read_message


class MessageTestCase(TestCase):
    """Test message construction/destruction functions."""

    def test_checksum(self):
        """Tests checksum calculation."""
        message = bytes.fromhex("55 aa 01 89 00 00 04 55 0c 00 00")
        checksum = bytes.fromhex("01 ee")
        self.assertEqual(checksum, calculate_checksum(message))

    def test_construct(self):
        """Tests message construction."""
        identifier = b'\x06\x01\x02'
        payload = b'\x10\x10'
        expect = bytes.fromhex("55 aa 06 01 02 00 02 10 10 01 2a")
        self.assertEqual(expect, construct_message(identifier, payload))

    def test_read(self):
        """Tests read_message function."""
        f = BytesIO(bytes.fromhex("55 aa 06 01 02 00 02 10 10 01 2a"))
        ident, payload = read_message(f)
        self.assertEqual(b"\x06\x01\x02", ident)
        self.assertEqual(b"\x10\x10", payload)


message = b"\x55\xaa\x00\x01\x02\x00\x00\x01\x02"  # Sample inverter message


class InverterConnectionTestCase(TestCase):
    """Test low-level send/receive inverter messages over a socket connection.

    These test cases exist mainly because the sockets might behave differently
    in Windows.
    """

    def setUp(self) -> None:
        """Creates socket pair for local (app) and remote ('real' inverter) side."""
        local_sock, remote_sock = socketpair()  # We apparently can't use family=AF_INET on Linux
        local_sock.settimeout(1.0)
        remote_sock.settimeout(1.0)
        self.inverter = Inverter(local_sock, None)
        # This sock mimics the actual inverter, i.e. the remote side of the
        #  connection. Send messages on it to mimic the actual inverter sending
        #  messages to the Inverter class.
        self.sock = remote_sock

    def tearDown(self) -> None:
        """Closes the sockets to prevent warnings."""
        self.inverter.sock.close()
        self.sock.close()

    def test_eof_on_send(self):
        """Tests if exception is raised on sending when connection is closed."""
        self.sock.close()  # Mimic inverter closed connection
        with self.assertRaises(BrokenPipeError):
            self.inverter.send(b"\x00\x01\x02", b"")

    def test_eof_on_recv(self):
        """Tests if exception is raised for closed connection when receiving."""
        self.sock.close()  # Mimic inverter closed connection
        with self.assertRaises(InverterEOFError):
            self.inverter.receive()

    def test_multiple_messages_received_at_once(self):
        """Multiple messages might arrive at once for TCP sockets."""
        # Send 2 messages
        self.sock.send(message + message)
        # Receive them back
        ident, payload = self.inverter.receive()
        self.assertEqual(b"\x00\x01\x02", ident)
        self.assertEqual(b"", payload)
        ident, payload = self.inverter.receive()
        self.assertEqual(b"\x00\x01\x02", ident)
        self.assertEqual(b"", payload)

    def test_chopped_message(self):
        """Messages might arrive chopped for TCP sockets."""
        queue = Queue()
        # Receive the message in a separate thread, because it blocks
        thread = Thread(target=lambda q: q.put(self.inverter.receive()), args=(queue,))
        thread.start()
        self.sock.send(message[0:1])  # Send some message parts
        sleep(0.01)
        self.sock.send(message[1:3])
        sleep(0.01)
        self.sock.send(message[3:7])
        sleep(0.01)
        self.sock.send(message[7:])
        thread.join()
        # Check result
        ident, payload = queue.get(timeout=1.0)
        self.assertEqual(b"\x00\x01\x02", ident)
        self.assertEqual(b"", payload)

    def test_send(self):
        """Tests whether a message from the app will arrive at the receiver."""
        self.inverter.send(b"\x00\x01\x02", b"")
        received_message = self.sock.recv(4096)
        self.assertEqual(message, received_message)

    def test_disconnect_multiple(self):
        """Tests if disconnect can be called multiple times."""
        self.inverter.disconnect()
        self.inverter.disconnect()  # Should not raise exception

    def test_disconnect_closed(self):
        """Tests if disconnect can be called on a closed socket."""
        self.sock.close()
        self.inverter.sock.close()
        self.inverter.sock_file.close()
        self.inverter.disconnect()  # Should not raise exception


class InverterFinderTestCase(TestCase):
    def test_inverter_not_found(self):
        """Tests if InverterNotFoundError is raised."""
        with InverterFinder() as finder:
            with self.assertRaises(InverterNotFoundError):
                finder.find_inverter(advertisements=2, interval=0.01)

    def test_new_connection(self):
        """Tests if a new connection is returned."""
        with InverterFinder() as finder:
            sock1 = create_connection(('127.0.0.1', 1200))
            sock2, addr = finder.find_inverter()
        # Test if the 2 sockets are paired
        sock2.send(b"\x12")
        self.assertEqual(b"\x12", sock1.recv(1))
        sock1.close()
        sock2.close()

    # noinspection PyMethodMayBeStatic
    def test_enter(self):
        """Tests if context manager __enter__ can safely be called twice."""
        finder = InverterFinder()
        finder.listen()
        with finder:
            pass