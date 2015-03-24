import logging
import socket

class PCM(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.logger = logging.getLogger('PCM')
        self.logger.setLevel(loglevel)

        self.EOL = '\r\n'

        self.host = self.actor.config.get('pcm', 'host')
        self.port = int(self.actor.config.get('pcm', 'port'))

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
            cmd.warn('text="failed to create socket to PCM: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to PCM: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.err as e:
            cmd.warn('text="failed to read response from PCM: %s"' % (e))
            raise

        self.logger.debug('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def pcmCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

    def motorsCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "~32/1%s" % (cmdStr)
        
        ret = self.sendOneCommand(fullCmd, cmd)

        if len(ret) < 3:
            raise RuntimeError("command response is too short!")

        if ret[:2] != '/0':
            raise RuntimeError("command response header is wrong: %s" % (ret))

        status = ord(ret[2])
        rest = ret[3:]

        errCode = status & 0x0f
        ok = (errCode == 0)
        busy = status & 0x20
        if status & 0x90:
            raise RuntimeError("unexpected response top nibble in %x" % (status))
            
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



