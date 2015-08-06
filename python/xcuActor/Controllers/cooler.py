import logging
import socket
import time

import numpy as np

class cooler(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('cooler')
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        # self.host = self.actor.config.get('cooler', 'host')
        # self.port = int(self.actor.config.get('cooler', 'port'))

        self.host = '10.1.1.57'
        self.port = 10001

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
            cmd.warn('text="failed to create socket to cooler: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to cooler: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from cooler: %s"' % (e))
            raise

        if not ret.startswith(fullCmd):
            cmd.warn('text="command to cooler (%r) was not echoed: %r"' % (fullCmd,
                                                                           ret))
            raise

        reply = ret[len(fullCmd):].strip()
        
        self.logger.debug('received %r', reply)
        cmd.diag('text="received %r"' % reply)
        s.close()

        return reply

    def getPID(self, cmd=None):
        KP = float(self.sendOneCommand('KP'))
        KI = float(self.sendOneCommand('KI'))
        KD = float(self.sendOneCommand('KD'))
        mode = self.sendOneCommand('COOLER')
        setPower = float(self.sendOneCommand('PWOUT'))

        if cmd is not None:
            cmd.inform('coolerLoop=%s, %g,%g,%g' % (mode,
                                                    KP, KI,KD))
        return mode, KP, KI, KD
    
    def startCooler(self, setpoint, cmd=None):
       ret = self.sendOneCommand('LOGIN=STIRLING')
       ret = self.sendOneCommand('TTARGET=%g' % (setpoint))
       ret = self.sendOneCommand('COOLER=ON')
       ret = self.sendOneCommand('LOGOUT=STIRLING')

       self.status(cmd=cmd)
        
    def getTemps(self, cmd=None):
        power = float(self.sendOneCommand('P'))
        headTemp = float(self.sendOneCommand('TC'))
        baseTemp = float(self.sendOneCommand('TEMP RJ'))
        setTemp = float(self.sendOneCommand('TTARGET'))

        if cmd is not None:
            cmd.inform('coolerTemps=%g,%g,%g, %g' % (setTemp,
                                                     baseTemp, headTemp,
                                                     power))
            
    def status(self, cmd=None):
        self.getPID(cmd=cmd)
        self.getTemps(cmd=cmd)
        
    def rawCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

