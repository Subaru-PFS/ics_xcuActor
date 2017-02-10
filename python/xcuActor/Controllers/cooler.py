import logging
import socket
import time

import numpy as np

import xcuActor.Controllers.bufferedSocket as bufferedSocket
reload(bufferedSocket)

class cooler(object):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL='\r\n')

        self.keepUnlocked = False
        self.sock = None
        
    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def connectSock(self, cmd):
        if self.sock is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
            except socket.error as e:
                cmd.warn('text="failed to create socket for %s: %s"' % (self.name, e))
                raise
 
            try:
                s.connect((self.host, self.port))
            except socket.error as e:
                cmd.warn('text="failed to connect to %s: %s"' % (self.name, e))
                raise
            self.sock = s
            
        return self.sock

    def closeSock(self, cmd):
        if self.sock is not None:
            try:
                self.sock.close()
            except socket.error as e:
                cmd.warn('text="failed to close socket for %s: %s"' % (self.name, e))
            
        self.sock = None
        
    def sendOneCommand(self, cmdStr, doClose=True, cmd=None):
        """ Send one command and return one response.

        Args
        ----
        cmdStr : str
           The cryocooler command to send.
        doClose : bool
           If True (the default), the device socket is closed before returning.
       
        Returns
        -------
        str : the single response string, with EOLs stripped.

        Raises
        ------
        IOError : from any communication errors.
        """
        
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        s = self.connectSock(cmd)
        
        try:
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to send to cooler: %s"' % (e))
            raise

        ret = self.ioBuffer.getOneResponse(sock=s, cmd=cmd)
        if not ret.startswith(cmdStr):
            cmd.warn('text="command to cooler (%r) was not echoed: %r"' % (fullCmd,
                                                                           ret))
            raise

        reply = self.getOneResponse(cmd=cmd)
        if doClose:
            self.closeSock(cmd)

        return reply

    def getOneResponse(self, sock=None, cmd=None, timeout=None):
        if sock is None:
            sock = self.connectSock(cmd)
            
        ret = self.ioBuffer.getOneResponse(sock=sock, timeout=timeout, cmd=cmd)
        reply = ret.strip()
        
        self.logger.debug('received %r', reply)
        if cmd is not None:
            cmd.diag('text="received %r"' % reply)

        return reply

    def unlock(self, doClose=True, cmd=None):
        self.sendOneCommand('LOGIN=STIRLING', doClose=doClose, cmd=cmd)

    def lock(self, cmd):
        if not self.keepUnlocked:
            self.sendOneCommand('LOGOUT=STIRLING', cmd=cmd)
        
    def getPID(self, cmd=None):
        KP = float(self.sendOneCommand('KP', doClose=False, cmd=cmd))
        KI = float(self.sendOneCommand('KI', doClose=False, cmd=cmd))
        KD = float(self.sendOneCommand('KD', doClose=False, cmd=cmd))
        mode = self.sendOneCommand('COOLER', doClose=False, cmd=cmd)

        if cmd is not None:
            cmd.inform('coolerLoop=%s, %g,%g,%g' % (mode,
                                                    KP, KI,KD))
        return mode, KP, KI, KD
    
    def startCooler(self, mode, setpoint, cmd=None):
        headTemp = float(self.sendOneCommand('TC', cmd=cmd))

        if headTemp > 350:
            cmd.fail('text="the cryocooler temperature is too high (%sK). Check the temperature sense cable."' % (headTemp))
            return

        self.unlock()
        
        if mode is 'power':
            ret = self.sendOneCommand('PWOUT=%g' % (setpoint), doClose=False, cmd=cmd)
            ret = self.sendOneCommand('COOLER=POWER', doClose=False, cmd=cmd)
            pass
        else:
            ret = self.sendOneCommand('TTARGET=%g' % (setpoint), doClose=False, cmd=cmd)
            ret = self.sendOneCommand('COOLER=ON', doClose=False, cmd=cmd)

        self.lock(cmd=cmd)

        self.status(cmd=cmd)

        if cmd:
            cmd.finish()
        
    def stopCooler(self, cmd=None):
        ret = self.sendOneCommand('LOGIN=STIRLING', doClose=False)
        ret = self.sendOneCommand('COOLER=OFF', doClose=False)
        self.sendOneCommand('LOGOUT=STIRLING', doClose=False)

        self.status(cmd=cmd)

    def getTemps(self, cmd=None):
        power = float(self.sendOneCommand('P', doClose=False))
        tipTemp = float(self.sendOneCommand('TC', doClose=False))
        rejectTemp = float(self.sendOneCommand('TEMP2', doClose=False))
        setTemp = float(self.sendOneCommand('TTARGET'))

        if cmd is not None:
            cmd.inform('coolerTemps=%g,%g,%g, %g' % (setTemp,
                                                     rejectTemp, tipTemp,
                                                     power))

        return setTemp, rejectTemp, tipTemp, setTemp
    
    def status(self, cmd=None):
        ret = []
        
        ret1 = self.getPID(cmd=cmd)
        ret2 = self.getTemps(cmd=cmd)

        ret.extend(ret1)
        ret.extend(ret2)

        return ret
        
    def rawCmd(self, cmdStr, timeout=None, cmd=None):
        """ Send a raw command to the controller and return the output.

        Args
        ----
        cmdStr : str
           The command string to send. We add some EOL, but otherwise do not modify this.
        timeout : float or None
           If not None, keep waiting up to this amount of time for new response lines. Once
           nothing is returned the commoan output is considered complete.

        Returns:
        list of strings.
        """
        
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, doClose=(timeout is None), cmd=cmd)
        retLines = [ret]
        if timeout is not None:
            s = self.connectSock(cmd)

            while True:
                ret = self.getOneResponse(sock=s, timeout=timeout, cmd=None)
                if not ret:
                    break
                retLines.append(ret)
            self.closeSock(cmd)
            
        return retLines

