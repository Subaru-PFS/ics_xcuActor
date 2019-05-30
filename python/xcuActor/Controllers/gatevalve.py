#!/usr/bin/env python

from importlib import reload

import logging
import sys
import time

import rtdADIO.ADIO
reload(rtdADIO.ADIO)

class gatevalve(object):
    def __init__(self, actor, name,
                 logger=None,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.logger = logger if logger else logging.getLogger('gatevalve')
        self.logger.setLevel(loglevel)

        self.bits = dict(sam_off=0x20,
                         sam_return=0x10,
                         enabled=0x8,
                         active=0x4,
                         closed=0x2,
                         open=0x1)
        self.bitnames = {v:k for k, v in self.bits.items()}
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

        self.dev = None
        self.dev = rtdADIO.ADIO.ADIO(self.bits['enabled'] | self.bits['sam_off'] | self.bits['sam_return'])
        # This is the second argument, for the interrupt mask. Add it when we update rtdADIO.
        #self.posBits | self.bits['enabled'] | self.bits['active'])


    def __del__(self):
        if self.dev is not None:
            self.dev.disconnect()
        
    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        try:
            self.dev.disconnect()
        except:
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
            return (status & self.posBits) == self.bits['open']

        try:
            ret = self.spinUntil(isOpen, starting=starting, wait=wait, cmd=cmd)
        except Exception as e:
            cmd.warn(f'text="FAILED to open gatevalve: {e}; Trying to set requested state to closed...."')
            ret = self.close(cmd=cmd)
            raise

        self.status(cmd=cmd)
        return ret
        
    def close(self, wait=4, cmd=None):
        """ Drop the gatevalve Open Enable line. """

        starting = self.status(cmd=cmd)
        self.dev.clear(self.bits['enabled'])

        def isClosed(status):
            return (status & self.posBits) == self.bits['closed']
            
        try:
            ret = self.spinUntil(isClosed, starting=starting, wait=wait, cmd=cmd)
        except Exception as e:
            cmd.warn(f'text="FAILED to close gatevalve: {e}"')
            raise
        
        self.status(cmd=cmd)
        return ret

    def request(self, toOpen):
        """ Raise or drop the gatevalve open request line. """

        if toOpen:
            self.dev.set(self.bits['enabled'])
        else:
            self.dev.clear(self.bits['enabled'])
            
    def powerOffSam(self, wait=1, cmd=None):
        """ Assert SAM power off. """
        starting = self.status(cmd=cmd)
        self.dev.set(self.bits['sam_off'])

        def isSamOff(status):
            return bool(status & self.bits['sam_off'])
            
        ret = self.spinUntil(isSamOff, starting=starting, wait=wait, cmd=cmd)
        return ret
        
    def powerOnSam(self, wait=1, cmd=None):
        """ Deassert SAM power line, turning it on. """
        starting = self.status(cmd=cmd)
        self.dev.clear(self.bits['sam_off'])

        def isSamOn(status):
            return not bool(status & self.bits['sam_off'])
            
        ret = self.spinUntil(isSamOn, starting=starting, wait=wait, cmd=cmd)
        return ret
        
    def getStatus(self):
        return self.dev.status()

    def describeStatus(self, bits):
        """ Return the description of the position and the requested position. """
        
        rawPos = bits & self.posBits
        pos = self.positionNames[rawPos]
        rawRequest = bits & self.requestBits
        request = self.requestNames[rawRequest]
        samPower = not bool(self.bits['sam_off'] & bits)

        return pos, request, samPower
        
    def status(self, silentIf=None, cmd=None):
        ret = self.getStatus()
        pos, request, samPower = self.describeStatus(ret)
        if cmd and ret != silentIf:
            cmd.inform('gatevalve=0x%02x,%s,%s' % (ret, pos, request))
            cmd.inform('samPower=%d' % (samPower))

        return ret

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, str):
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
    
        print("status=0x%02x,%s,%s" % (stat0,
                                       pos, request))

    _status(gv)
    if args.open:
        gv.open()
    if args.close:
        gv.close()
    _status(gv)

if __name__ == "__main__":
    main()
    
