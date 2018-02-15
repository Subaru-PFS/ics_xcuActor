from builtins import range
from builtins import object
import logging
import socket
import time

from opscore.utility.qstr import qstr

class rough(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = b'\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        try:
            cmdStr = cmdStr.encode('latin-1')
        except AttributeError:
            pass
        
        fullCmd = b"%s%s" % (cmdStr, self.EOL)
        self.logger.info('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
        except socket.error as e:
            cmd.warn('text="failed to create socket to rough: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to rough: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from rough: %s"' % (e))
            raise

        self.logger.info('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def parseReply(self, cmdStr, reply, cmd=None):
        cmdType = cmdStr[:1]

        if cmdType == b'?':
            replyFlag = b'='
        elif cmdType == b'!':
            replyFlag = b'*'

        replyStart = reply[:5]
        replyCheck = replyFlag + cmdStr[1:5]
        if not reply.startswith(replyCheck):
            cmd.warn('text=%s' % qstr('reply to command %r is the unexpected %r (vs %r)' % (cmdStr,
                                                                                            replyStart,
                                                                                            replyCheck)))
        
        return reply[5:].strip().split(b';')
    
    def ident(self, cmd=None):
        cmdStr = b'?S801'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startPump(self, cmd=None):
        cmdStr = b'!C802 1'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def stopPump(self, cmd=None):
        cmdStr = b'!C802 0'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startStandby(self, percent=90, cmd=None):
        cmdStr = b"!S805 %d" % (percent)
        ret = self.sendOneCommand(cmdStr, cmd=cmd)

        cmdStr = b"!C803 1"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret
    
    def stopStandby(self, cmd=None):
        cmdStr = b"!C803 0"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret

    def statusWord(self, status, cmd=None):
        flags = ('Fail',
                 'Below stopped speed',
                 'Above normal speed',
                 'Vent valve energized',
                 'Start command active',
                 'Serial enable active',
                 'Standby active',
                 'Above 50% full speed',
                 'Parallel control mode',
                 'Serial control mode',
                 'Invalid podule software',
                 'Podule failed',
                 'Failed to reach speed within timer',
                 'Overspeed or overcurrent tripped',
                 'Pump internal temp. system failure',
                 'Serial enable is inactive',
                 'bit 17',
                 'bit 18',
                 'bit 19',
                 'bit 20',
                 'bit 21',
                 'bit 22',
                 'bit 23',
                 'bit 24',
                 'bit 25',
                 'bit 26',
                 'bit 27',
                 'bit 28',
                 'bit 29',
                 'bit 30',
                 'bit 31')

        allFlags = []
        for i in range(32):
            if status & (1 << i):
                allFlags.append(flags[i])

        if cmd is not None:
            cmd.inform('roughStatus=0x%08x,%r' % (status, ', '.join(allFlags)))

        return allFlags
                 
    def speed(self, cmd=None):
        cmdStr = b'?V802'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        status = self.parseReply(cmdStr, ret, cmd=cmd)

        rpm =  int(status[0]) * 60
        status = int(status[1], base=16)
        
        cmd.inform('roughSpeed=%s' % (rpm))
        self.statusWord(status, cmd=cmd)
        
        return rpm, status
        
    def pumpTemps(self, cmd=None):
        cmdStr = b'?V808'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        speeds = self.parseReply(cmdStr, ret, cmd=cmd)

        cmd.inform('roughTemps=%s,%s' % (speeds[0], speeds[1]))
        
        return speeds
        
    def status(self, cmd=None):
        reply = []
        
        speeds = self.speed(cmd=cmd)
        #VAW = self.pumpVAW(cmd=cmd)
        temps = self.pumpTemps(cmd=cmd)
        reply.extend(speeds)
        #reply.extend(VAW)
        reply.extend(temps)
        
        return reply

    def pumpCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

