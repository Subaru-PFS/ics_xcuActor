import logging
import socket
import time

class gauge(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))
        self.busID = 1
        
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
            cmd.warn('text="failed to create socket to %s: %s"' % (self.name, e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to %s: %s"' % (self.name, e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from %s: %s"' % (self.name, e))
            raise

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret
    
    def gaugeCrc(self, s):
        return sum([ord(c) for c in s]) % 256

    def gaugeRawCmd(self, cmdStr, cmd=None):
        cmdStr = '%03d%s' % (self.busID, cmdStr)
        crc = self.gaugeCrc(cmdStr)
        cmdStr = '%s%03d' % (cmdStr, crc)

        ret = self.sendOneCommand(cmdStr, cmd=cmd)

        return ret

    def gaugeRawQuery(self, code, cmd=None):
        cmdStr = '00%03d02=?' % (code)
        return self.gaugeRawCmd(cmdStr, cmd=None)
    
    def pressure(self, cmd=None):
        data_out = self.gaugeRawQuery(740)

        # 001 10 740 06 430022 030
        mantissa = int(data_out[10:14]) * 10.0 ** -3 
        exponent = int(data_out[14:16]) - 20

        # convert to torr
        reading = 0.750061683 * (mantissa * 10**exponent) 

        return reading

    def gaugeCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        # ret = self.sendOneCommand(cmdStr, cmd)
        ret = self.gaugeRawCmd(cmdStr, cmd=cmd)
        return ret

