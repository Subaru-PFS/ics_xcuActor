import logging
import socket
import time

from opscore.utility.qstr import qstr

class pump(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('pump')
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get('pump', 'host')
        self.port = int(self.actor.config.get('pump', 'port'))

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
        except socket.error as e:
            cmd.warn('text="failed to create socket to pump: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to pump: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.err as e:
            cmd.warn('text="failed to read response from pump: %s"' % (e))
            raise

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def parseReply(self, cmdStr, reply, cmd=None):
        cmdType = cmdStr[0]

        if cmdType == '?':
            replyFlag = '='
        elif cmdType == '!':
            replyFlag = '*'

        replyStart = reply[:5]
        replyCheck = replyFlag + cmdStr[1:5]
        if not reply.startswith(replyCheck):
            cmd.warn('text=%s' % qstr('reply to command %r is the unexpected %r (vs %r)' % (cmdStr,
                                                                                            replyStart,
                                                                                            replyCheck)))
        
        return reply[5:].strip().split(';')
    
    def ident(self, cmd=None):
        cmdStr = '?S851'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startPump(self, cmd=None):
        cmdStr = '!C852 1'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def stopPump(self, cmd=None):
        cmdStr = '!C852 0'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def speed(self, cmd=None):
        cmdStr = '?V852'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        speeds = self.parseReply(cmdStr, ret, cmd=cmd)

        rpm =  int(speeds[0]) * 60
        cmd.inform('speed=%s' % (rpm))
        
        return speeds
        
    def pumpTemps(self, cmd=None):
        cmdStr = '?V859'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        speeds = self.parseReply(cmdStr, ret, cmd=cmd)

        cmd.inform('pumpTemps=%s,%s' % (speeds[0], speeds[1]))
        
        return speeds
        
    def pumpVAW(self, cmd=None):
        cmdStr = '?V860'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        pumpStat = self.parseReply(cmdStr, ret, cmd=cmd)

        V, A, W = [float(i) for i in pumpStat]
        V /= 10.0
        A /= 10.0
        W /= 10.0

        if cmd is not None:
            cmd.inform('pumpVAW=%g,%g,%g' % (V,A,W))
            
        return V,A,W
        
    def status(self, cmd=None):
        reply = []
        
        speeds = self.speed(cmd=cmd)
        VAW = self.pumpVAW(cmd=cmd)
        temps = self.pumpTemps(cmd=cmd)
        reply.extend(speeds)
        reply.extend(VAW)
        reply.extend(temps)
        
        return reply

    def pumpCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

