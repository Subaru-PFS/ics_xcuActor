from importlib import reload

import logging
import socket
import time

from xcuActor.Controllers import idgPfeiffer
reload(idgPfeiffer)

class PCM(object):
    powerPorts = ('motors', 'gauge', 'cooler', 'temps',
                  'bee', 'fee', 'interlock', 'heaters')
    
    def __init__(self, actor=None, name='PCM',
                 loglevel=logging.INFO, host='10.1.1.4', port=1000):

        self.name = name
        self.logger = logging.getLogger()
        self.logger.setLevel(loglevel)
        self.EOL = b'\n'

        self.actor = actor
        if actor is not None:
            self.host = self.actor.actorConfig[self.name]['host']
            self.port = self.actor.actorConfig[self.name]['port']
        else:
            self.host = host
            self.port = port

        self.gauge = idgPfeiffer.Pfeiffer(self.name)
        self.logger.warn('gauge=%s,%s', 'new', self.gauge)

    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        pass

    def sendOneCommand(self, cmdStr, timeout=2.0, cmd=None):
        try:
            cmdStr = cmdStr.encode('latin-1')
        except AttributeError:
            pass
        
        fullCmd = b"%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', cmdStr)
        if cmd is not None:
            cmd.diag('text="sending %r"' % (cmdStr))

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
        except socket.error as e:
            self.logger.error('text="failed to create socket to PCM: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            self.logger.error('text="failed to create connect or send to PCM: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            self.logger.error('text="failed to read response from PCM: %s"' % (e))
            raise

        self.logger.debug('received: %r', ret)
        s.close()

        if cmd is not None:
            cmd.diag('text="received %r"' % (ret))
            
        if ret.startswith(b'Error:'):
            raise RuntimeError('Error reading or writing: %s' % (ret))

        return ret

    def systemInPowerMask(self, mask, system):
        portIndices = {name:i for i,name in enumerate(self.powerPorts)}

        return mask & (1 << portIndices[system])
    
    def pcmStatus(self, cmd=None):
        if cmd is not None:
            cmd.inform('powerNames=%s' % (self.powerPorts))
            
    def pcmCmd(self, cmdStr, timeout=None, cmd=None):
        return self.sendOneCommand(cmdStr, timeout=timeout, cmd=cmd)
    
    def powerCmd(self, system, turnOn=True, cmd=None):
        try:
            i = self.powerPorts.index(system)
        except IndexError:
            self.logger.error('text="not a known power port: %s"' % (system))
            return False

        cmdStr = b"~se,ch%d,%s" % (i+1, b'on' if turnOn else b'off')
        ret = self.sendOneCommand(cmdStr)
        return ret

    def powerOn(self, system):
        print(self.powerCmd(system, turnOn=True))

    def powerOff(self, system):
        print(self.powerCmd(system, turnOn=False))

    def parseMotorResponse(self, ret):
        if len(ret) < 3:
            raise RuntimeError("command response is too short!")

        if ret.startswith(b'NO RESPONSE'):
            raise RuntimeError("no response to command: %s" % (ret))
        
        if ret[:2] != b'/0':
            raise RuntimeError("command response header is wrong: %s" % (ret))

        status = ret[2]
        rest = ret[3:].decode('latin-1')

        errCode = status & 0x0f
        busy = not(status & 0x20)
        if status & 0x90:
            raise RuntimeError("unexpected response top nibble in %x" % (status))

        self.logger.debug("ret=%s, status=%0x, errCode=%0x, busy=%s",
                          ret, status, errCode, busy)
        return errCode, status, busy, rest

    def _waitForIdle(self, maxTime=15.0, cmd=None):
        if cmd is not None:
            cmd.diag('text="waiting %0.3fs for idle"' % (maxTime))
        t0 = time.time()
        t1 = time.time()
        while True:
            ret = self.sendOneCommand(b"~@,T1000,/1Q")
            _, _, busy, _ = self.parseMotorResponse(ret)
            if not busy:
                if cmd is not None:
                    cmd.diag('text="not busy after %0.2fs"' % (t1-t0))
                return True
            if maxTime is not None and t1-t0 >= maxTime:
                if cmd is not None:
                    cmd.diag('text="still busy after %0.2fs"' % (t1-t0))
                return False
            time.sleep(0.1)
            t1 = time.time()

        return False

    def waitForIdle(self, maxTime=15.0, cmd=None):
        try:
            return self._waitForIdle(maxTime=maxTime, cmd=cmd)
        except RuntimeError as e:
            if not str(e).startswith('no response to command:'):
                raise
            cmd.diag('text="restarting idle wait: %s"' % (e))
            time.sleep(0.25)
            return self._waitForIdle(maxTime=1.0, cmd=cmd)

    def motorsCmd(self, cmdStr,
                  waitForIdle=False, returnAfterIdle=False,
                  maxTime=10.0, waitTime=1.0, cmd=None):

        if isinstance(cmdStr, str):
            cmdStr = cmdStr.encode('latin-1')
        if waitForIdle:
            ok = self.waitForIdle(maxTime=waitTime, cmd=cmd)
            if not ok:
                return "timed out when waiting for idle controller", True, ''
            
        fullCmd = b"~@,T%d,/1%s" % (int(maxTime*1000), cmdStr)
        
        ret = self.sendOneCommand(fullCmd, cmd=cmd)
        errCode, status, busy, rest = self.parseMotorResponse(ret)

        errStrings = ["OK",
                      "Init Error",
                      "Bad Command",
                      "Bad Operand",
                      "Code#4",
                      "Communications Error",
                      "Code#6",
                      "Not Initialized",
                      "Code#8",
                      "Overload",
                      "Code#10",
                      "Move Not Allowed",
                      "Code#12",
                      "Code#13",
                      "Code#14",
                      "Controller Busy"]
        try:
            errStr = errStrings[errCode]
        except IndexError:
            errStr = errCode

        if errStr != 'OK':
            return errStr, busy, rest

        if returnAfterIdle:
            idle = self.waitForIdle(maxTime=maxTime, cmd=cmd)
                
            busy = not idle
            if not idle:
                self.logger.warn('text="motor controller busy for %s after motor command"' % (maxTime))
                errStr = "timed out while waiting for idle controller"
                
        return errStr, busy, rest

    def sendGaugeCommand(self, gaugeStr, cmd=None):
        gaugeCmdTimeout = 5     # s
        pcmCmd = b'~@,T%d,' % (gaugeCmdTimeout * 1000)
        gaugeCmdStr = pcmCmd + gaugeStr

        ret = self.sendOneCommand(gaugeCmdStr, timeout=gaugeCmdTimeout + 1, cmd=cmd)
        gaugeRet = self.gauge.parseResponse(ret, None, cmd)

        return gaugeRet

    def gaugeRawCmd(self, cmdStr, cmd=None):
        gaugeStr = self.gauge.makeRawCmd(cmdStr, cmd=cmd)
        return self.sendGaugeCommand(gaugeStr, cmd=cmd)
