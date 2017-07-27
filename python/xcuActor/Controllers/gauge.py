from __future__ import absolute_import

import logging
import socket
import time

from xcuActor.Controllers import pfeiffer
reload(pfeiffer)

class gauge(pfeiffer.Pfeiffer):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))

        pfeiffer.Pfeiffer.__init__(self)
        
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

    def gaugeRawCmd(self, cmdStr, cmd=None):
        gaugeStr = self.gaugeMakeRawCmd(cmdStr, cmd=cmd)
        ret = self.sendOneCommand(gaugeStr, cmd=cmd)

        return ret

    def gaugeCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        # ret = self.sendOneCommand(cmdStr, cmd)
        ret = self.gaugeRawCmd(cmdStr, cmd=cmd)
        return ret

