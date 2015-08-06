import logging
import socket
import time

import numpy as np

from opscore.utility.qstr import qstr

class ionpump(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('ionpump')
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get('ionpump', 'host')
        self.port = int(self.actor.config.get('ionpump', 'port'))

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def calcCrc(self, s):
        crc = reduce(int.__xor__, [ord(c) for c in s])
        return crc
        
    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        coreCmd = "\x80%s\x03" % (cmdStr)
        crc = self.calcCrc(coreCmd)
        fullCmd = "\x02%s%02x" % (coreCmd, crc)
        self.logger.info('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

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
        cmd.diag('text="received %r"' % ret)
        s.close()

        reply = self.parseRawReply(ret)

        return reply

    def parseRawReply(self, raw):
        if len(raw) < 6:
            raise RuntimeError("too short reply: %r" % (raw))

        head = raw[:2]
        tail = raw[-3:]
        
        if head[0] != '\x02':
            raise RuntimeError("reply header is not x02: %r" % (raw))
        crc = self.calcCrc(raw[1:-2])
        wantTail = '\x03%02X' % (crc)
        if tail != wantTail:
            raise RuntimeError("reply tail/crc is not %r: %r" % (wantTail,
                                                                 raw))

        return raw[2:-3]
    
    def sendReadCommand(self, win, cmd=None):
        if not isinstance(win, str):
            win = "%03d" % (win)
        reply = self.sendOneCommand(win+'0', cmd=cmd)

        if reply[:3] != win:
            raise RuntimeError("win in reply is not %s: %r" % (win,
                                                               reply))
        if reply[3] != '0':
            raise RuntimeError("reply is not for a read: %r" % (reply))

        return reply[4:]
            
    def sendWriteCommand(self, win, value, cmd=None):
        if not isinstance(win, str):
            win = "%03d" % (win)
        reply = self.sendOneCommand(win+'1'+value, cmd=cmd)

        return reply

    def readTemp(self, channel):
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
            reply = self.sendReadCommand(win)
        except:
            reply = np.nan
            
        return float(reply)
        
    def readVoltage(self, channel):
        try:
            reply = self.sendReadCommand(800 + 10*channel)
        except:
            reply = np.nan
            
        return float(reply)
        
    def readCurrent(self, channel):
        try:
            reply = self.sendReadCommand(801 + 10*channel)
        except:
            reply = np.nan

        return float(reply)
        
    def readPressure(self, channel):
        try:
            reply = self.sendReadCommand(802 + 10*channel)
        except:
            reply = np.nan

        return float(reply)
        
    def readEnabled(self, channel):
        reply = self.sendReadCommand(10 + channel)
        return int(reply)
    
    def readOnePump(self, channel, cmd=None):
        enabled = self.readEnabled(channel)
        if enabled:
            V = self.readVoltage(channel)
            A = self.readCurrent(channel)
            p = self.readPressure(channel)
        else:
            V = A = p = np.nan
            
        if cmd is not None:
            cmd.inform('ionPump%d=%d,%g,%g,%g' % (channel,
                                                  enabled,
                                                  V,A,p))

        return enabled,V,A,p
            
    def status(self, cmd=None):
        reply = []
        
        speeds = self.speed(cmd=cmd)
        VAW = self.pumpVAW(cmd=cmd)
        temps = self.pumpTemps(cmd=cmd)
        reply.extend(speeds)
        reply.extend(VAW)
        reply.extend(temps)
        
        return reply
