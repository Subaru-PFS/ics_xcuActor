#!/usr/bin/env python

import logging
import sys
import time

import rtdADIO.ADIO

class gatevalve(object):
    def __init__(self, actor, name,
                 logger=None,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.logger = logger if logger else logging.getLogger('gatevalve')
        self.logger.setLevel(loglevel)

        self.bits = dict(enabled=0x8,
                         active=0x4,
                         closed=0x2,
                         open=0x1)
        self.bitnames = {v:k for k, v in self.bits.iteritems()}
        self.posBits = self.bits['open'] | self.bits['closed']
        self.positionNames = {self.bits['open']:'open',
                              self.bits['closed']:'closed',
                              0:'unknown',
                              self.posBits:'invalid'}
        self.requestBits = self.bits['enabled'] | self.bits['active']
        self.requestNames = {self.bits['enabled']:'blocked',
                             self.bits['active']:'invalid',
                             0:'closed',
                             self.requestBits:'open'}

        self.dev = rtdADIO.ADIO(self.bits['enabled'])
                                # logger=self.logger)

    def __del__(self):
        self.dev.disconnect()
        
    def start(self):
        pass

    def stop(self, cmd=None):
        self.dev.disconnect()

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
            return (status & self.posBits) == self.bits['open']
            
        ret = self.spinUntil(isOpen, starting=starting, wait=wait, cmd=cmd)
        return ret
        
    def close(self, wait=4, cmd=None):
        """ Drop the gatevalve Open Enable line. """

        starting = self.status(cmd=cmd)
        self.dev.clear(self.bits['enabled'])

        def isClosed(status):
            return (status & self.posBits) == self.bits['closed']
            
        ret = self.spinUntil(isClosed, starting=starting, wait=wait, cmd=cmd)
        return ret

    def getStatus(self):
        return self.dev.status()

    def describeStatus(self, bits):
        """ Return the description of the position and the requested position. """
        
        rawPos = bits & self.posBits
        pos = self.positionNames[rawPos]
        rawRequest = bits & self.requestBits
        request = self.requestNames[rawRequest]

        return pos, request
        
    def status(self, silentIf=None, cmd=None):
        ret = self.getStatus()
        pos, request = self.describeStatus(ret)
        if cmd and ret != silentIf:
            cmd.inform('gatevalve=0x%02x,%s,%s' % (ret, pos, request))

        return ret

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, basestring):
        import shlex
        argv = shlex.split(argv)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--close', action='store_true')

    args = parser.parse_args(argv)

    gv = gatevalve(None, gatevalve)
    def _status(gv):
        stat0 = gv.status()
        pos, request = gv.describeStatus(stat0)
    
        print "status=0x%02x,%s,%s" % (stat0,
                                       pos, request)

    _status(gv)
    if args.open:
        gv.open()
    if args.close:
        gv.close()
    _status(gv)

if __name__ == "__main__":
    main()
    
