import logging
import socket
import time

class gauge(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('gauge')
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get('gauge', 'host')
        self.port = int(self.actor.config.get('gauge', 'port'))

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
            cmd.warn('text="failed to create socket to gauge: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to gauge: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from gauge: %s"' % (e))
            raise

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def pressure(self, cmd=None):
        cmdStr = '0010074002=?106'

        data_out = self.sendOneCommand(cmdStr, cmd=cmd)
        
        mantissa = int(data_out[10:14]) * 10 ** -3 
        exponent = int(data_out[14:16]) - 20

        # convert to torr
        reading = 0.750061683 * (mantissa * 10**exponent) 

        return reading

    def gaugeCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

