import logging
import socket
import time

class temps(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        
        self.host = self.actor.config.get('temps', 'host')
        self.port = int(self.actor.config.get('temps', 'port'))

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
            cmd.warn('text="failed to create socket to temps: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to temps: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from temps: %s"' % (e))
            raise

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def tempsCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

    def fetchTemps(self, sensors=None, cmd=None):
        if sensors is None:
            sensors = range(12)

        replies = ["nan"]*12
        for s_i in sensors:
            replies[s_i] = self.sendOneCommand('?K%d' % (s_i + 1))
        values = [float(s) for s in replies]

        return values
    
