import logging
import socket
import time

import numpy as np

from opscore.utility.qstr import qstr
from functools import reduce

class ionpump(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = b'\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))
        self.busID = int(self.actor.config.get(self.name, 'busID'))
        self.pumpIDs = [int(ID) for ID in self.actor.config.get('ionpump', 'pumpids').split(',')]

    @property
    def npumps(self):
        return len(self.pumpIDs)
    
    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        pass

    def calcCrc(self, s):
        crc = reduce(int.__xor__, [c for c in s])
        return crc
        
    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        try:
            cmdStr = cmdStr.encode('latin-1')
        except AttributeError:
            pass
        
        busID = bytes([128 + int(self.busID)])
        coreCmd = b"%s%s\x03" % (busID, cmdStr)
        crc = self.calcCrc(coreCmd)
        fullCmd = b"\x02%s%02X" % (coreCmd, crc)
        self.logger.info('sending %r to %s:%s', fullCmd, self.host, self.port)
        cmd.diag('text="%s sending %s"' % (self.name, fullCmd))

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
        except socket.error as e:
            cmd.warn('text="failed to create socket to ion pump: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to ion pump: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from ion pump: %s"' % (e))
            raise

        self.logger.info('received %r', ret)
        cmd.diag('text="ionpump received %r"' % ret)
        s.close()

        reply = self.parseRawReply(ret)

        return reply

    def parseRawReply(self, raw):
        if len(raw) < 6:
            raise RuntimeError("too short reply: %r" % (raw))

        head = raw[:2]
        tail = raw[-3:]
        
        if head[:1] != b'\x02':
            raise RuntimeError("reply header is not x02: %r" % (raw))
        crc = self.calcCrc(raw[1:-2])
        wantTail = b'\x03%02X' % (crc)
        if tail != wantTail:
            raise RuntimeError("reply tail/crc is not %r: %r" % (wantTail,
                                                                 raw))

        return raw[2:-3]
    
    def sendReadCommand(self, win, cmd=None):
        if isinstance(win, int):
            win = b"%03d" % (win)
        elif isinstance(win, str):
            win = win.encode('latin-1')

        reply = self.sendOneCommand(win+b'0', cmd=cmd)

        if reply[:3] != win:
            raise RuntimeError("win in reply is not %s: %r" % (win,
                                                               reply))
        if reply[3:4] != b'0':
            raise RuntimeError("reply is not for a read: %r" % (reply))

        return reply[4:]
            
    def sendWriteCommand(self, win, value, cmd=None):
        if isinstance(win, int):
            win = b"%03d" % (win)
        elif isinstance(win, str):
            win = win.encode('latin-1')

        reply = self.sendOneCommand(win+b'1'+value.encode('latin-1'), cmd=cmd)

        return reply

    def readTemp(self, channel, cmd=None):
        if channel == 1:
            win = 801
        elif channel == 2:
            win = 802
        elif channel == 3:
            win = 808
        elif channel == 4:
            win = 809
        else:
            raise RuntimeError("unknown channel %s" % (channel))
        
        try:
            reply = self.sendReadCommand(win, cmd=cmd)
        except:
            reply = np.nan
            
        return float(reply)
        
    def readVoltage(self, channel, cmd=None):
        try:
            reply = self.sendReadCommand(800 + 10*channel, cmd=cmd)
        except:
            reply = np.nan
            
        return float(reply)
        
    def readCurrent(self, channel, cmd=None):
        try:
            reply = self.sendReadCommand(801 + 10*channel, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)
        
    def readPressure(self, channel, cmd=None):
        try:
            reply = self.sendReadCommand(802 + 10*channel, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)
        
    def _onOff(self, newState, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps on or off, and report the status. """

        graceTime = 2.0
        if newState:
            try:
                graceTime = float(self.actor.config.get('ionpump', 'delay'))
            except:
                pass
            
        ret = []
        for c_i, c in enumerate(self.pumpIDs):
            if c_i == 0 and not pump1:
                continue
            if c_i == 1 and not pump2:
                continue
            retCmd = self.sendWriteCommand(10+c, '%s' % (int(newState)), cmd=cmd)
            ret.append(retCmd)
            time.sleep(graceTime)
        
        for c_i, c in enumerate(self.pumpIDs):
            self.readOnePump(c_i, cmd=cmd)

        return ret
    
    def off(self, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps off, and report the status. """

        return self._onOff(False, pump1=pump1, pump2=pump2, cmd=cmd)

    def on(self, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps on, and report the status. """

        return self._onOff(True, pump1=pump1, pump2=pump2, cmd=cmd)

    def readEnabled(self, channel, cmd=None):
        reply = self.sendReadCommand(10 + channel, cmd=cmd)
        return int(reply)

    
    def readError(self, channel, cmd=None):
        """ Read the error mask for a single channel, or the union of all. 
        
        Args
        ----
        channel - int
          1-4 for an individual channel, or 0 for the OR of all

        Returns
        -------
        mask - the errors as detailed in Table 13 of the 4UHV manual.
        """
        
        self.sendWriteCommand(505, '%06d' % (channel), cmd=cmd)
        reply = self.sendReadCommand(206, cmd=cmd)
        return int(reply)

    errorBits = {0x0001:"Fan error",
                 0x0002:"HV power input error",
                 0x0004:"PFC power input error",
                 0x0008:"PFC overtemp",
                 0x0010:"CPU-HV communication error",
                 0x0020:"Interlock cable",
                 0x0040:"HV overtemp",
                 0x0080:"Protection error",
                 0x0100:"Measurement error",
                 0x0200:"HV output error",
                 0x0400:"Short circuit",
                 0x0800:"HV disabled",
                 0x1000:"0x1000",
                 0x2000:"0x2000",
                 0x4000:"0x4000",
                 0x8000:"Suspect live channel"}
    
    def _makeErrorString(self, err):
        """ Return a string describing all error bits, or 'OK'. """

        if err == 0:
            return "OK"
        errors = []
        for i in range(16):
            mask = 1 << i
            if err & mask:
                errors.append(self.errorBits[mask])

        return ",".join(errors)
        
    def readOnePump(self, channelNum, cmd=None):
        channel = self.pumpIDs[channelNum]
        enabled = self.readEnabled(channel)

        V = self.readVoltage(channel, cmd=cmd)
        A = self.readCurrent(channel, cmd=cmd)
        p = self.readPressure(channel, cmd=cmd)
        t = self.readTemp(channel, cmd=cmd)

        err = self.readError(channel, cmd=cmd)

        # INSTRM-594, INSTRM-758: create synthetic error when pump is on but not indicating current or pressure.
        if enabled and (V == 0 or A == 0 or p == 0):
            err |= 0x8000

        if cmd is not None:
            cmdFunc = cmd.inform if err == 0 else cmd.warn
            errString = self._makeErrorString(err)
            
            cmdFunc('ionPump%d=%d,%g,%g,%g, %g' % (channelNum+1,
                                                   enabled,
                                                   V,A,t,p))
            cmdFunc('ionPump%dErrors=0x%04x,%s' % (channelNum+1, err, qstr(errString)))
                
        return enabled,V,A,p
