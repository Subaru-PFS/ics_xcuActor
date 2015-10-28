import logging
import socket
import time

import numpy as np

import rtdADIO.ADIO

class gatevalve(object):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.logger = logging.getLogger('gatevalve')
        self.logger.setLevel(loglevel)

        self.bits = {0x1:'open',
                     0x2:'closed',
                     0x4:'xxx',
                     0x8:'enabled')
        
        self.dev = rtdADIO.ADIO(0x8)

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def open(self, wait=5, cmd=None):
        """ Raise the gatevalve Open Enable line. """

        state0 = self.getStatus()
        ret = self.dev.set(0x8)

        def isOpen(status):
            status & 0x2
            
        ret = self.spinUntil(isOpen, wait=wait, cmd=cmd)
        return ret
        
    def close(self, wait=5, cmd=None):
        """ Drop the gatevalve Open Enable line. """

        state = get.getStatus()
        ret = self.dev.clear(0x8)

        def isClosed(status):
            status & 0x1
            
        ret = self.spinUntil(isClosed, wait=wait, cmd=cmd)
        return ret

    def getStatus(self):
        return self.dev.status()

    def status(self, cmd=None):
        ret = self.dev.getStatus()
        if cmd:
            cmd.inform('gatevalve=0x%02x,%s' % (ret,
                                                qstr(self.describeStatus(ret))))
        return ret
