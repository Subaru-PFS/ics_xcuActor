import logging
import socket
import time

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
                 loglevel=logging.INFO):

        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.device = None if keepOpen else False
        
        self.EOL = EOL

    def connect(self, cmd=None):
        if self.device:
            return self.device
        
        s = self._connect(cmd=cmd)

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
        
    def _connect(self, cmd=None):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)   # Set 
        except Exception as e:
            if cmd is not None:
                cmd.warn('text="failed to create socket to %s: %s"' % (self.name, e))
            raise
 
        try:
            s.connect((self.host, self.port))
        except Exception as e:
            if cmd is not None:
                cmd.warn('text="failed to connect socket to %s: %s"' % (self.name, e))
            raise

        return s

    def readOneLine(self, s=None, timeout=1.0, cmd=None):
        if s is None:
            s = self.connect(cmd=cmd)
            
        lastTimeout = s.gettimeout()
        if timeout != lastTimeout:
            s.setTimeout(timeout)
            
        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from %s: %s"' % (self.name, e))
            raise

        s.close()
        
        return ret

    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        s = self.connect()
        
        try:
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create send command to %s: %s"' % (self.name, e))
            raise

        ret = s.recv(1024)
        s.close()

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)

        return ret.strip()

class temps(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('temps')
        self.logger.setLevel(loglevel)

        self.EOL = '\n'
        
        host = self.actor.config.get('temps', 'host')
        port = int(self.actor.config.get('temps', 'port'))

        self.dev = SocketIO(host, port, name, self.EOL,
                            keepOpen=False,
                            loglevel=loglevel)
        
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

        s = self.connect()
        
        try:
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create send command to %s: %s"' % (self.name, e))
            raise

        ret = s.recv(1024)
        s.close()

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)

        return ret

    def sendImage(self, path, cmd=None, verbose=True):
        """ Download an image file. """

        req = '\xB2\xA5\x65\0x4B'
        conf = '\x69\xD3\x0D\x26'
        ack = '\x4D\x5A\x9A\xB4'
        nak = '\x2D\x59\x5A\xB2'

        self.actor.controllers['PCM'].powerOff('temps')
        time.sleep(0.5)
        self.actor.controllers['PCM'].powerOn('temps')
        
        for i in range(100):
            try:
                dev = self.dev.connect()
            except:
                if i == 99:
                    raise RuntimeError('text="could not connect to a temp controller to flahs it."')
                time.sleep(0.1)
                continue

            dev.settimeout(0.1)
            cmd.inform('text="connected to temps controller after %d loops"' % (i))
            break
                
        for i in range(100):
            try:
                dev.send(req)
                ret = dev.recv(len(conf))
            except:
                ret = None
                time.sleep(0.1)
                
            if ret:
                if ret == conf:
                    cmd.inform('text="handshake done, after %d loops"' % (i))
                    break
                else:
                    cmd.warn('text="handshake failed. received %r"' % (ret))
                    time.sleep(0.1)

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

                cmd.diag('text="srec %d: %s"' (lineNumber, l))

                devChars = bytearray(2+2+len(sdata_s)/2)
                devChars[0:2] = stype_s
                devChars[2:4] = chr(slen_s)
                for c_i in range(slen_s):
                    devChars[c_i+4] = chr(int(sdata_s[2*c_i:2*c_i+2], base=16))

                if verbose or lineNumber%100 == 1:
                    self.logger.info('sending line %d / %d', lineNumber, len(lines))
                    if cmd is not None:
                        cmd.inform('text="sending line %d / %d"', lineNumber, len(lines))
                self.logger.debug("sending command :%r:", devChars)
                dev.send(devChars)
                ret = dev.recv(len(ack))
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

        ret = self.dev.sendOneCommand(cmdStr, cmd)
        return ret

    def fetchTemps(self, sensors=None, cmd=None):
        if sensors is None:
            sensors = range(12)

        replies = ["nan"]*12
        for s_i in sensors:
            replies[s_i] = self.dev.sendOneCommand('?K%d' % (s_i + 1), cmd=cmd)
        values = [float(s) for s in replies]

        return values
    
