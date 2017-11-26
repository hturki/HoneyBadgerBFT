#!/usr/bin/python

import gevent
from gevent import monkey
monkey.patch_all()

from gevent.queue import *
from gevent.server import StreamServer
from gevent import Greenlet
import ast
import cPickle as pickle
import os
import socket
import socks
import struct
import sys

from honeybadgerbft.crypto.threshsig import boldyreva
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT

from socket import error as SocketError

def to_serialized_element(x,y):
    import base64
    import binascii
    evenify = lambda x: '0' + x if len(x)%2 == 1 else x
    x = binascii.unhexlify(evenify("%x" % x))
    y = binascii.unhexlify(evenify("%x" % y))
    return "1:" + base64.b64encode(x+y)

def read_keyshare_file(filename, deserialize, N=4):
    """
    This parsing routine is unique to the demo output of the DKG program.
    It returns a master VK, and a share VK for each party

    param deserialize: 
        boldyreva.group.deserialize or tpke.group.deserialize
    Return VK, VKs, SK
    """
    lines = open(filename).readlines()
    idx = 0
    while not 'Pubkey 0' in lines[idx]:
        idx += 1
    VKs = []
    for i in range(N+1):
        line = lines[idx+1+i*3]
        line = ast.literal_eval(line[2:])
        print line
        x,y = line
        VKs.append(deserialize(to_serialized_element(x,y),0))
    # second to last line is share
    SK = int(lines[-1].split(':')[-1])
    return VKs[0], VKs[1:], SK

BASE_PORT = 49500
WAITING_SETUP_TIME_IN_SEC = 3

def goodread(f, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        buf.append(f.read(ltmp))
        ltmp -= len(buf[-1])
    return ''.join(buf)

def goodrecv(sock, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        m = sock.recv(length)
        if len(m) == 0: # File closed
            assert False
        buf.append(m)
        ltmp -= len(buf[-1])
    return ''.join(buf)

def listen_to_channel(port):
    # Returns a queue we can read from
    print 'Preparing server on %d...' % port
    q = Queue()
    def _handle(socket, address):
        while True:
            try:
                msglength, = struct.unpack('<I', goodrecv(socket, 4))
                line = goodrecv(socket, msglength)
            except AssertionError:
                print 'Receive Failed!'
                return
            obj = decode(line)
            sender, payload = obj
            # TODO: authenticate sender using TLS certificate
            q.put( (sender, payload) )

    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, myID):
    # Returns a queue we can write to
    print 'Trying to connect to %s as party %d' % (repr((hostname, port)), myID)
    s = socks.socksocket()
    q = Queue()
    def _run():
        retry = True
        while retry:
            try:
                s = socks.socksocket()
                s.connect((hostname, port))
                retry = False
            except Exception, e:  # socks.SOCKS5Error:
                retry = True
                gevent.sleep(1)
                s.close()
                print 'retrying (%s, %d) caused by %s...' % (hostname, port, str(e))
        print 'Connection established (%s, %d)' % (hostname, port)
        while True:
            obj = q.get()
            try:
                content = encode((myID,obj))
            except TypeError:
                print obj
                raise
            try:
                s.sendall(struct.pack('<I', len(content)) + content)
            except SocketError:
                print '!! [to %d] sending %d bytes' % (myID, len(content))
                break
        print 'closed channel'
    gtemp = Greenlet(_run)
    gtemp.parent_args = (hostname, port, myID)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

def exception(msg):
    print "Exception: %s" % msg
    os.exit(1)

def encode(m):
    return pickle.dumps(m)

def decode(s):
    return pickle.loads(s)

sendConnection = None

def run_badger_node(myID, N, f, sPK, sSK, ePK, eSK, sendPath, receivePath):
    '''
    Test for the client with random delay channels
    :param i: the current node index
    :param N: the number of parties
    :param t: the number of malicious parties toleranted
    :return None:
    '''
    assert type(sPK) is boldyreva.TBLSPublicKey
    assert type(sSK) is boldyreva.TBLSPrivateKey
    assert type(ePK) is tpke.TPKEPublicKey
    assert type(eSK) is tpke.TPKEPrivateKey

    # Create the listening channel
    recv_queue = listen_to_channel(BASE_PORT + myID)
    recv = recv_queue.get
    print 'server started'

    # Create the sending channels
    send_queues = []
    for i in range(N):
        port = BASE_PORT + i
        send_queues.append(connect_to_channel('127.0.0.1', port, myID))
    def send(j, obj):
        send_queues[j].put(obj)

    # Start the honeybadger instance
    tx_submit = Queue()

    def send_to_hyperledger(transactions):
        global sendConnection
        for tx in transactions:
            if os.path.exists(sendPath):
                if sendConnection is None:
                    print "Opening sending socket at path " + sendPath
                    sendConnection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sendConnection.connect(sendPath)
                print "sending length " + str(len(tx))
                sendConnection.send(struct.pack('!Q', len(tx)))
                print "sending tx " + tx
                sendConnection.send(tx)

    hbbft = HoneyBadgerBFT("sid", myID, 8, N, f,
                           sPK, sSK, ePK, eSK,
                           send, recv,
                           tx_submit.get, send_to_hyperledger,
                           encode=repr, decode=ast.literal_eval)
    th = Greenlet(hbbft.run)
    th.parent_args = (N, f)
    th.name = __file__+'.honestParty(%d)' % i
    th.start()

    if os.path.exists(receivePath):
        os.remove(receivePath)

    print "Opening listening socket at path " + receivePath
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(receivePath)

    # Listen for incoming connections
    server.listen(1)

    while True:
        # Wait for a connection
        connection, client_address = server.accept()
        try:
            while True:
                message = connection.recv(8)
                if message:
                    print "Message " + message
                    length, = struct.unpack('!Q', message)
                    print length
                    message = connection.recv(length)
                    print message
                    tx_submit.put([message])
                else:
                    print >> sys.stderr, 'no more data from', client_address
                    break

        finally:
            # Clean up the connection
            connection.close()
            os.remove(receivePath)

    th.join()

import atexit
def exit():
    print "Entering atexit()"

if __name__ == '__main__':
    
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-i", "--index", dest="i",
                      help="Node index (1 through -N)", metavar="I", type="int")
    parser.add_option("-s", "--send-path", dest="sendPath",
                      help="Path to use for unix socket that sends messages to Hyperledger", metavar="PATH", type="str")
    parser.add_option("-r", "--receive-path", dest="receivePath",
                      help="Path to use for unix socket that listens for messages from Hyperledger", metavar="PATH", type="str")
    (options, args) = parser.parse_args()

    N = 4
    f = 1
    if not options.i:
        parser.error('Please specify the arguments')
        sys.exit(1)
    assert 1 <= options.i <= 4
    myID = options.i-1
    print myID

    while True:
        try:
            sVK, sVKs, sSK = read_keyshare_file('dkg/DKG_0.8.0/DKG-Executable/ss512/node%d/keys.out'%(myID+1), tpke.group.deserialize)
            eVK, eVKs, eSK = read_keyshare_file('dkg/DKG_0.8.0/DKG-Executable/ss512/node%d/keys.out'%(myID+1), tpke.group.deserialize)
        except IOError, e:
            gevent.sleep(1) # Waiting for keys
            continue
        break
    print 'OK!'
    ePK = tpke.TPKEPublicKey(N, f+1, eVK, eVKs)
    eSK = tpke.TPKEPrivateKey(N, f+1, eVK, eVKs, eSK, myID)
    sPK = boldyreva.TBLSPublicKey(N, f+1, sVK, sVKs)
    sSK = boldyreva.TBLSPrivateKey(N, f+1, sVK, sVKs, sSK, myID)

    run_badger_node(myID, N, f, sPK, sSK, ePK, eSK, options.sendPath, options.receivePath)
    
