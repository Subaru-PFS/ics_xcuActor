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

class pcmUdp(object):
    def __init__(self, actor, name,
                 host='10.1.1.4', port=1025,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger('PcmUdp')
        self.logger.setLevel(loglevel)

        self.host = host
        self.port = port

        self.udpListener = None

    def translateKeyVal(self, rawKey, rawVal):
        key = rawKey
        
        try:
            val = int(rawVal)
        except ValueError:
            try:
                val = float(rawVal)
            except:
                self.logger.warn('text="failed to convert UDP value for %s: %r:"' % (rawKey, rawVal))

        if key in ('P',):
            val *= 51.715
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
                
    def status(self, cmd):
        """ Generate all keywords. """

        for k in 'IO', 'T', 'P':
            cmd.inform("%s=%s" % (k, self.dataStore.get(k, None)))

        kl = []
        for k in ('MD1', 'MD2', 'MD3'):
            kl.append("%s=%s" % (k, self.dataStore.get(k, None)))
        cmd.inform("; ".join(kl))

        kl = []
        for k in ('ML1', 'ML2', 'ML3'):
            kl.append("%s=%s" % (k, self.dataStore.get(k, None)))
        cmd.inform("; ".join(kl))

        kl = []
        for k in ('m1', 'm2', 'm3'):
            kl.append("%s=%s" % (k, self.dataStore.get(k, None)))
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
                self.logger.info('%s=%s' % (key, val))
                self.dataStore[key] = val
                self.actor.bcast.inform('%s=%s' % (key, val))
        
    def datagramReceived(self, data, addr):
        try:
            data = data.strip()
            key, val = data.split(':')
        except Exception as e:
            self.logger.warn('text="failed to parse UDP message from %s: %r"' % (addr, data))
            return

        self.updateVal(key, val)
        
    def start(self):
        self.stop()

        self.dataStore = OrderedDict()
        pcm = PcmListener()
        pcm.wireIn(self, self.host, self.port)
        self.udpListener = pcm
        self.logger.info('text="wiring in listener"')
        try:
            reactor.listenUDP(self.port, pcm)
        except Exception, e:
            raise RuntimeError("Failed reactor.listenUdp: %s" % (e))

        self.logger.info('text="wired in listener"')
        return True
    
    def stop(self, cmd=None):
        self.logger.info('text="unwiring listener"')
        if self.udpListener is not None:
            self.udpListener.transport.loseConnection()
            self.udpListener = None
            

def _doRunRun(pcm, reactor):
    pcm.start()
    reactor.run(installSignalHandlers=False)
    
def runPcmAndReactor():
    from twisted.internet import reactor
    from threading import Thread

    pcm = PcmUdp()
    reactorThread = Thread(target=_doRunRun, args=(pcm, reactor)).start()

    return pcm, reactorThread

def main(self):
    runPcmAndReactor()

if __name__ == "__main__":
    main()
    
