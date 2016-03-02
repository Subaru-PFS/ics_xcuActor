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
                 EOL='\n',
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

        fullCmd = "%s%s" % (cmdStr, self.EOL)
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

        self.actor = actor
        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        
        host = self.actor.config.get('temps', 'host')
        port = int(self.actor.config.get('temps', 'port'))

        self.dev = SocketIO(host, port, name, self.EOL,
                            keepOpen=False,
                            loglevel=loglevel)

        self.heaters = dict(spider=1, ccd=2)
        
    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def sendImage(self, path, cmd=None, verbose=True):
        """ Download an image file. """

        req = '\xB2\xA5\x65\x4B'
        conf = '\x69\xD3\x0D\x26'
        ack = '\x4D\x5A\x9A\xB4'
        nak = '\x2D\x59\x5A\xB2'

        self.logger.setLevel(0)
        self.logger.debug('kicking temps power')

        sock = self.dev.connect()
        sock.settimeout(0.05)
        
        if False:
            self.logger.debug('connecting to temps')
            for i in range(100):
                try:
                    sock = self.dev.connect(timeout=0.1)
                except Exception as e:
                    self.logger.debug("no connect: %s", e)
        else:
            self.logger.debug('resetting temps')
            self.dev.sendOneCommand('~E', sock=sock, cmd=cmd)

        self.logger.debug("handshaking done" % (i))
        for i in range(40):
            try:
                self.logger.debug("handshaking 0 %d" % (i))
                sock.send(req)
                self.logger.debug("handshaking 1 %d" % (i))
                ret = sock.recv(4)
            except Exception as e:
                self.logger.debug("handshaking %d: %s" % (i, e))
                ret = None
                time.sleep(0.02)
                continue
            
            self.logger.debug("handshaking 2 %s" % (ret))
            if ret:
                if ret == conf:
                    self.logger.debug("handshake done, after %d loops" % (i))
                    cmd.inform('text="handshake done, after %d loops"' % (i))
                    break
                else:
                    self.logger.debug("handshake %d failed: %r " % (i, ret))
                    cmd.warn('text="handshake failed. received %r"' % (ret))
                    time.sleep(0.1)
            else:
                self.logger.debug("handshake %d failed: %r " % (i, ret))
                time.sleep(0.1)

        if ret != conf:
            raise RuntimeError("did not receive flash conf'")

        logLevel = self.logger.level
        self.logger.setLevel(logging.INFO)
        with open(path, 'rU') as hexfile:
            lines = hexfile.readlines()
            t0 = time.time()
            self.logger.info('sending image file %s, %d lines' % (path, len(lines)))
            if cmd is not None:
                cmd.inform('text="sending image file %s, %d lines"' % (path, len(lines)))
            lineNumber = 0
            for l in lines:
                lineNumber += 1
                l = l.strip()
                stype_s = l[0:2]
                slen_s = l[2:4]
                sdata_s = l[4:]

                slen = int(slen_s, base=16)
                if slen != len(sdata_s)/2:
                    raise RuntimeError("wrong length: %d vs %d" % (slen, len(sdata_s)/2))

                self.logger.info('text="srec %d: %s"' % (lineNumber, l))
                # cmd.diag('text="srec %d: %s"' % (lineNumber, l))
                try:
                    devChars = bytearray(2+2+slen)
                    devChars[0:2] = stype_s
                    devChars[2:4] = slen_s
                    for c_i in range(slen):
                        devChars[c_i+4] = chr(int(sdata_s[2*c_i:2*c_i+2], base=16))
                except Exception as e:
                    cmd.warn('text="oops: %s"' % (e))
                    
                if verbose or lineNumber%100 == 1:
                    self.logger.info('sending line %d / %d', lineNumber, len(lines))
                    if cmd is not None:
                        cmd.inform('text="sending line %d / %d"' % (lineNumber, len(lines)))
                self.logger.debug("sending command :%r:", devChars)
                sock.send(devChars)
                self.logger.debug("sent: %r:", devChars)
                ret = sock.recv(len(ack))
                self.logger.debug("rcvd: %r", ret)
                if ret == nak:
                    if cmd is not None:
                        cmd.warn('text="NAK after sending line %d"' % (lineNumber))
                    raise RuntimeError("NAK after sending line %d" % (lineNumber))
                if ret != ack:
                    if cmd is not None:
                        cmd.warn('text="unexpected response (%r) after sending line %d"' %
                                 (ret, lineNumber))
                    raise RuntimeError("unexpected response (%r) after sending line %d" %
                                       (ret, lineNumber))

            t1 = time.time()
            self.logger.info('sent image file %s in %0.2f seconds' % (path, t1-t0))
            if cmd is not None:
                cmd.inform('sent image file %s in %0.2f seconds' % (path, t1-t0))

        self.logger.setLevel(logLevel)

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
                                                               self.heaters.keys()))

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

        enabled = []
        atLevel = []
        for heaterNum in range(2):
            enabled0 = self.dev.sendOneCommand('?L%d' % (heaterNum+1), cmd=cmd)
            atLevel0 = self.dev.sendOneCommand('?V%d' % (heaterNum+1), cmd=cmd)

            enabled.append(int(enabled0))
            atLevel.append(float(atLevel0))

        maxLevel = float(0xfff)
        
        if cmd is not None:
            cmd.inform('heaters=%d,%d,%0.3f,%0.3f' % (enabled[0],
                                                      enabled[1],
                                                      atLevel[0]/maxLevel,
                                                      atLevel[1]/maxLevel))
        return enabled + atLevel
        
    def fetchTemps(self, sensors=None, cmd=None):
        if sensors is None:
            sensors = range(12)

        replies = ["nan"]*12
        for s_i in sensors:
            replies[s_i] = self.dev.sendOneCommand('?K%d' % (s_i + 1), cmd=cmd)
        values = [float(s) for s in replies]

        return values
