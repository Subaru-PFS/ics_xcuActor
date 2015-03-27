import logging
from collections import OrderedDict

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

class PcmListener(DatagramProtocol):

    def wireIn(self, owner, host, port):
        self.owner = owner
        self.pcmHost = host
        self.pcmPort = port

    def datagramReceived(self, data, addr):
        self.owner.datagramReceived(data, addr)

    def startProtocol(self):
        print "startProtocol!"
        # self.transport.connect(self.pcmHost, self.pcmPort)

    def stopProtocol(self):
        print "stopProtocol!"
        
    def connectionLost(self):
        print "connectionLost!"

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

    def filterVal(self, key, val, lastVal):
        keep = True

        if lastVal is None:
            keep = True
        else:
            if ((key[0] == 'I' and abs(val - lastVal) < 0.1) or
                (key in {'IL', 'IH'} and abs(val - lastVal) < 0.15) or
                (key[0] == 'V' and abs(val - lastVal) < 0.2) or
                (key == 'T' and abs(val - lastVal) < 0.4) or
                (key == 'P' and abs(val - lastVal) < 0.1)):

                keep = False

        return keep
                
    def udpStatus(self, cmd):
        """ Generate all keywords. """

        for k in 'IO', 'T', 'P':
            cmd.inform("%s=%s" % (k, self.dataStore[k]))

        kl = []
        for k in ('MD1', 'MD2', 'MD3'):
            kl.append("%s=%s" % (k, self.dataStore[k]))
        cmd.inform("; ".join(kl))

        kl = []
        for k in ('ML1', 'ML2', 'ML3'):
            kl.append("%s=%s" % (k, self.dataStore[k]))
        cmd.inform("; ".join(kl))

        kl = []
        for k in ('m1', 'm2', 'm3'):
            kl.append("%s=%s" % (k, self.dataStore[k]))
        cmd.inform("; ".join(kl))

    def clearKeys(self, keys):
        """ Force updates of a given list of keys. """

        if keys is None:
            self.dataStore.clear()
        else:
            for k in keys:
                del self.dataStore[k]

    def updateVal(self, rawKey, rawVal):
        key, val = self.translateKeyVal(rawKey, rawVal)
        
        lastVal = self.dataStore.get(key, None)
        if val != lastVal:
            keep = self.filterVal(key, val, lastVal)
            if keep:
                self.actor.bcast.inform('%s=%s' % (key, val))
                self.dataStore[key] = val
        
    def datagramReceived(self, data, addr):
        # now = time.time()

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
        pcm = PcmListener()
        pcm.wireIn(self, self.host, self.port)
        self.actor.bcast.warn('text="wiring in listener"')
        reactor.listenUDP(self.port, pcm)

    def stop(self, cmd=None):
        self.actor.bcast.warn('text="unwiring listener"')
        if self.udpListener is not None:
            self.udpListener.stopListening()
            self.udpListener = None
            
