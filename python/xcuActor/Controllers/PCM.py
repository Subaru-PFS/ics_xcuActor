import logging
import socket
import time

class PCM(object):
    powerPorts = ('motors', 'gauge', 'cooler', 'temps',
                  'bee', 'fee', 'interlock', 'heaters')
    
    def __init__(self, actor=None, name='unknown',
                 loglevel=logging.INFO, host='10.1.1.4', port=1000):

        self.logger = logging.getLogger()
        self.logger.setLevel(loglevel)
        self.EOL = '\r\n'

        self.actor = actor
        if actor is not None:
            self.host = self.actor.config.get('pcm', 'host')
            self.port = int(self.actor.config.get('pcm', 'port'))
        else:
            self.host = host
            self.port = port

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def sendOneCommand(self, cmdStr, cmd=None):
        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        if cmd is not None:
            cmd.diag('text="sending %r"' % (fullCmd))

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
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

        self.logger.debug('received: %s' % (ret))
        s.close()

        if cmd is not None:
            cmd.diag('text="received %r"' % (ret))
            
        if ret.startswith('Error:'):
            raise RuntimeError('Error reading or writing: %s' % (ret))

        return ret

    def pcmStatus(self, cmd=None):
        if cmd is not None:
            cmd.inform('powerNames=%s' % (self.powerPorts))
            
    def pcmCmd(self, cmdStr, cmd=None):
        return self.sendOneCommand(cmdStr, cmd=cmd)
    
    def powerCmd(self, system, turnOn=True, cmd=None):
        try:
            i = self.powerPorts.index(system)
        except IndexError:
            self.logger.error('text="not a known power port: %s"' % (system))
            return False

        cmdStr = "~se,ch%d,%s" % (i+1, 'on' if turnOn else 'off')
        ret = self.sendOneCommand(cmdStr)
        return ret

    def powerOn(self, system):
        print self.powerCmd(system, turnOn=True)

    def powerOff(self, system):
        print self.powerCmd(system, turnOn=False)

    def parseMotorResponse(self, ret):
        if len(ret) < 3:
            raise RuntimeError("command response is too short!")

        if ret[:2] != '/0':
            raise RuntimeError("command response header is wrong: %s" % (ret))

        status = ord(ret[2])
        rest = ret[3:]

        errCode = status & 0x0f
        busy = not(status & 0x20)
        if status & 0x90:
            raise RuntimeError("unexpected response top nibble in %x" % (status))

        self.logger.debug("ret=%s, status=%0x, errCode=%0x, busy=%s",
                          ret, status, errCode, busy)
        return errCode, status, busy, rest

    def waitForIdle(self, maxTime=15.0, cmd=None):
        t0 = time.time()
        t1 = time.time()
        while True:
            ret = self.sendOneCommand("~@,,/1Q", cmd=cmd)
            _, _, busy, _ = self.parseMotorResponse(ret)
            if not busy:
                return True
            if maxTime is not None and t1-t0 >= maxTime:
                return False
            time.sleep(0.1)
            t1 = time.time()

        return False

    def motorsCmd(self, cmdStr, waitForIdle=False, returnAfterIdle=False, maxTime=10.0, cmd=None):
        if waitForIdle:
            ok = self.waitForIdle(maxTime=maxTime, cmd=cmd)
        

        fullCmd = "~@,T2000,/1%s" % (cmdStr)
        
        ret = self.sendOneCommand(fullCmd, cmd=cmd)
        errCode, status, busy, rest = self.parseMotorResponse(ret)
        ok = errCode == 0

        if ok:
            errStr = "OK"
        else:
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
            errStr = errStrings[errCode]
            return errStr, busy, rest

        if returnAfterIdle:
            idle = self.waitForIdle(maxTime=maxTime)
            busy = not idle
            if not idle:
                self.logger.warn('text="motor controller busy for %s after motor command"' % (maxTime))

        return errStr, busy, rest

    def gaugeCrc(self, s):
        return sum([ord(c) for c in s]) % 256

    def gaugeRawCmd(self, cmdStr, cmd=None):
        crc = self.gaugeCrc(cmdStr)
        pcmCmd = '~@,T1500,'
        cmdStr = '%s%s%03d' % (pcmCmd, cmdStr, crc)

        ret = self.sendOneCommand(cmdStr, cmd=cmd)

        return ret

    def gaugeStatus(self, cmd=None):
        data_out = self.gaugeRawCmd('0010074002=?', cmd=cmd)
        
        mantissa = int(data_out[10:14]) * 10 ** -3 
        exponent = int(data_out[14:16]) - 20

        # convert to torr
        reading = 0.750061683 * (mantissa * 10**exponent) 

        return reading
        
