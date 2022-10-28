from importlib import reload

import numpy as np

import logging
import socket
import time

import xcuActor.Controllers.bufferedSocket as bufferedSocket
reload(bufferedSocket)

class NonClosingSocket(object):
    def __init__(self, s):
        self.s = s
    def close(self):
        return
    def __getattr__(self, attr):
        return getattr(self.s, attr)
        
class DeviceIO(object):
    def __init__(self, name,
                 EOL=b'\n',
                 keepOpen=False,
                 loglevel=logging.DEBUG):

        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.device = None if keepOpen else False
        self.EOL = EOL

    def connect(self, cmd=None, timeout=1.0):
        if self.device:
            return self.device
        
        s = self._connect(cmd=cmd, timeout=timeout)

        if self.device is None:
            self.device = s
            
        if self.device is False:
            return NonClosingSocket(s)
        else:
            return s
    
    def disconnect(self, cmd=None):
        if self.device in (None, False):
            return
        s = self.device
        self.device = None

        socket.socket.close(s)
        
class SocketIO(DeviceIO):
    def __init__(self, host, port, *argl, **argv):
        DeviceIO.__init__(self, *argl, **argv)
        self.host = host
        self.port = port

        self.ioBuffer = bufferedSocket.BufferedSocket('tempsio')
        
    def _connect(self, cmd=None, timeout=1.0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
        except Exception as e:
            if cmd is not None:
                cmd.warn('text="failed to create socket: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
        except Exception as e:
            if cmd is not None:
                cmd.warn('text="failed to connect socket%s"' % (e))
            raise

        return s

    def readOneLine(self, sock=None, timeout=1.0, cmd=None):
        if sock is None:
            sock = self.connect(cmd=cmd)
            
        ret = self.ioBuffer.getOneResponse(sock, timeout=timeout, cmd=cmd)
        
        sock.close()
        
        return ret

    def sendOneCommand(self, cmdStr, sock=None, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        if isinstance(cmdStr, str):
            cmdStr = cmdStr.encode('latin-1')
            
        fullCmd = b"%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        if sock is None:
            sock = self.connect()
        
        try:
            sock.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create send command to %s: %s"' % (self.name, e))
            raise

        ret = self.readOneLine(sock=sock, cmd=cmd)

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)

        return ret.strip()

class temps(object):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):

        self.name = name
        self.actor = actor
        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.EOL = b'\n'

        host = self.actor.actorConfig[self.name]['host']
        port = self.actor.actorConfig[self.name]['port']

        self.dev = SocketIO(host, port, name, self.EOL,
                            keepOpen=False,
                            loglevel=loglevel)

        self.heaters = dict(asic=1, ccd=2)

    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        pass

    def tempsCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.dev.sendOneCommand(cmdStr, cmd=cmd)
        return ret

    def heater(self, turnOn=None, heater=None, power=100, cmd=None):
        if turnOn not in (True, False):
            raise RuntimeError('turnOn argument (%s) is not True/False' % (turnOn))
        try:
            heaterNum = self.heaters[heater]
        except KeyError:
            raise RuntimeError('heater name (%s) is not %s' % (heater,
                                                               list(self.heaters.keys())))

        power = int(power) if turnOn else 0
        if power < 0 or power > 100:
            raise RuntimeError('heater power (%s) must be 0..100' % (power))
            
        self.dev.sendOneCommand('~L%d %d' % (heaterNum, turnOn), cmd=cmd)
        self.dev.sendOneCommand('~V%d %d' % (heaterNum, power), cmd=cmd)
            
        return self.fetchHeaters(cmd=cmd)
    
    def HPheater(self, turnOn=None, heaterNum=None, cmd=None):
        if turnOn not in (True, False):
            raise RuntimeError('turnOn argument (%s) is not True/False' % (turnOn))

        self.dev.sendOneCommand('~F%d %d' % (heaterNum, turnOn), cmd=cmd)
            
        return self.fetchHeaters(cmd=cmd)
    
    def fetchHeaters(self, cmd=None):
        """ Query all the heater states and levels. """
        
        enabled = []
        HPenabled = []
        atLevel = []
        for heaterNum in range(2):
            HPenabled0 = self.dev.sendOneCommand('?F%d' % (heaterNum+1), cmd=cmd)
            enabled0 = self.dev.sendOneCommand('?L%d' % (heaterNum+1), cmd=cmd)
            atLevel0 = self.dev.sendOneCommand('?V%d' % (heaterNum+1), cmd=cmd)

            HPenabled.append(int(HPenabled0))
            enabled.append(int(enabled0))
            atLevel.append(float(atLevel0))

        maxLevel = 1.0 # float(0xfff)
        
        if cmd is not None:
            cmd.inform('heaters=%d,%d,%0.3f,%0.3f,%d,%d,%0.3f,%0.3f' % (enabled[0], HPenabled[0],
                                                                        atLevel[0]/maxLevel, HPenabled[0],
                                                                        enabled[1], HPenabled[1],
                                                                        atLevel[1]/maxLevel, HPenabled[1]))
        return enabled + atLevel + HPenabled
        
    def fetchTemps(self, sensors=None, cmd=None):
        if sensors is None:
            sensors = list(range(12))

        replies = ["nan"]*12
        for s_i in sensors:
            replies[s_i] = self.dev.sendOneCommand('?K%d' % (s_i + 1), cmd=cmd)
        values = [float(s) for s in replies]

        return values
