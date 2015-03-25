import logging
import socket
from collections import OrderedDict
import time

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

class PcmListener(DatagramProtocol):

    def wireIn(self, owner, host, port):
        self.owner = owner
        self.pcmHost = host
        self.pcmPort = port

    def startProtocol(self):
        self.transport.connect(self.pcmHost, self.pcmPort)
        
    def datagramReceived(self, data, (host, port)):
        self.owner.datagramReceived(data)

class PcmUdp(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('PcmUdp')
        self.logger.setLevel(loglevel)

        self.host = self.actor.config.get('pcm', 'host')
        self.port = int(self.actor.config.get('pcm', 'udpport'))

        self.udpListener = None

    def translateKeyVal(self, rawKey, rawVal):
        key = rawKey
        
        try:
            val = int(rawVal)
        except ValueError:
            try:
                val = float(rawVal)
            except:
                self.actor.bcast.warn('text="failed to convert UDP value for %s: %r:"' % (rawKey, rawVal))

        return key, val
                
    def updateVal(self, rawKey, rawVal):
        key, val = self.translateKeyVal(rawKey, rawVal)
        
        lastVal = self.dataStore.get(key, None)
        if val != lastVal:
            if lastVal is None or key[0] not in {'P','T'}:
                self.actor.bcast.inform('%s=%s' % (key, val))

            self.dataStore[key] = val
        
    def datagramReceived(data, addr):
        now = time.time()

        try:
            data = data.strip()
            key, val = data.split(':')
        except Exception as e:
            self.actor.bcast.warn('text="failed to parse UDP message from %s: %r"' % (addr, data))
            return

        self.updateVal(key, val)
        
        
    def start(self):
        self.stop()

        self.dataStore = OrderedDict()
        reactor.listenUDP(0, PcmListener())

    def stop(self, cmd=None):
        if self.udpListener is not None:
            self.udpListener.stopListening()
            self.udpListener = None
            
