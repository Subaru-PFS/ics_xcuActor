import logging
import time

import rtdADIO.ADIO

class gatevalve(object):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.logger = logging.getLogger('gatevalve')
        self.logger.setLevel(loglevel)

        self.bits = dict(enabled=0x8,
                         closed=0x4,
                         open=0x2,
                         active=0x1)
        self.bitnames = {v:k for k, v in self.bitnames.iteritems()}
        self.posBits = self.bits['open'] | self.bits['closed']
        self.positionNames = {self.bits['open']:'open',
                              self.bits['closed']:'closed',
                              0:'unknown',
                              self.posBits:'invalid'}
        self.activeBits = self.bits['enabled'] | self.bits['active']

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def spinUntil(self, testFunc, starting=None, wait=5.0, cmd=None):
        """ """

        pause = 0.1
        lastState = starting
        while wait > 0:
            ret = self.status(silentIf=lastState, cmd=cmd)
            if testFunc(ret):
                return ret
            lastState = ret
            wait -= pause
            time.sleep(pause)
        raise RuntimeError("failed to get desired gate valve state. Timed out with: 0x%02x" % (ret))

    def open(self, wait=4, cmd=None):
        """ Raise the gatevalve Open Enable line. """

        starting = self.status(cmd=cmd)
        self.dev.set(self.bits['enabled'])

        def isOpen(status):
            status & self.posBits == self.bits['open']
            
        ret = self.spinUntil(isOpen, starting=starting, wait=wait, cmd=cmd)
        return ret
        
    def close(self, wait=4, cmd=None):
        """ Drop the gatevalve Open Enable line. """

        starting = self.status(cmd=cmd)
        self.dev.clear(self.bits['enabled'])

        def isClosed(status):
            status & self.posBits == self.bits['closed']
            
        ret = self.spinUntil(isClosed, starting=starting, wait=wait, cmd=cmd)
        return ret

    def getStatus(self):
        return self.dev.status()

    def describeStatus(self, bits):
        rawPos = bits & self.posBits
        pos = self.positionNames[rawPos]
        rawActive = bits & self.activeBits
        active = "unknown"

        return pos, active
        
    def status(self, silentIf=None, cmd=None):
        ret = self.dev.getStatus()
        if cmd and ret != silentIf:
            pos,active = self.describeStatus(ret)
            cmd.inform('gatevalve=0x%02x,%s,%s' % (ret, pos, active))

        return ret
