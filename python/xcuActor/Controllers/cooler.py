from importlib import reload
import logging
import socket
import time

import numpy as np

from opscore.utility.qstr import qstr

import xcuActor.Controllers.bufferedSocket as bufferedSocket
reload(bufferedSocket)

class cooler(object):
    def __init__(self, actor, name,
                 loglevel=logging.DEBUG):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = b'\r'

        self.host = self.actor.actorConfig[self.name]['host']
        self.port = self.actor.actorConfig[self.name]['port']

        self.ioBuffer = bufferedSocket.BufferedSocket(self.name + "IO", EOL=b'\r\n')

        self.keepUnlocked = False
        self.sock = None

        self.rejectLimitHit = False
        self.tipSensorBad = False

    def start(self, cmd=None):
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
        
    def sendOneCommand(self, cmdStr, doClose=True, cmd=None, timeout=None):
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

        if isinstance(cmdStr, str):
            cmdStr = cmdStr.encode('latin-1')

        fullCmd = b"%s%s" % (cmdStr, self.EOL)
        self.logger.debug('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        s = self.connectSock(cmd)
        
        try:
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to send to cooler: %s"' % (e))
            raise

        ret = self.ioBuffer.getOneResponse(sock=s, cmd=cmd)
        if not ret.startswith(cmdStr.decode('latin-1')):
            cmd.warn('text="command to cooler (%r) was not echoed: %r"' % (fullCmd,
                                                                           ret))
            raise

        reply = self.getOneResponse(cmd=cmd, timeout=timeout)
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
            cmd.inform('%sLoop=%s, %g,%g,%g' % (self.name, mode,
                                                KP, KI,KD))
        return mode, KP, KI, KD

    def startCooler(self, mode, setpoint, cmd=None):
        headTemp = float(self.sendOneCommand('TC', cmd=cmd))
        if headTemp > 350:
            cmd.fail('text="the %s cryocooler temperature is too high (%sK). Check the temperature sense cable."'
                     % (self.name, headTemp))
            return

        rejectTemp = float(self.sendOneCommand('TEMP2', cmd=cmd))
        rejectLimit = self.actor.actorConfig[self.name]['rejectLimit']
        if rejectTemp > rejectLimit:
            cmd.fail('text="the %s cryocooler reject temperature is too high (%sC). Check the coolant flow."'
                     % (name, rejectTemp))
            return

        self.rejectLimitHit = False

        self.unlock()
        
        if mode == 'power':
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
        
    def stopCooler(self, cmd=None, forceShutdown=False):
        """ Stop the cooler.

        Args
        ----
        cmd : `actorcore.Command`
           The controlling command
        name " `str`
           The device name.
        forceShutdown : `bool`
           Whether this done because of some status value.
        """
        
        ret = self.sendOneCommand('LOGIN=STIRLING', doClose=False)
        ret = self.sendOneCommand('COOLER=OFF', doClose=False)
        self.sendOneCommand('LOGOUT=STIRLING', doClose=False)
        self.rejectLimitHit = forceShutdown

        if not forceShutdown:
            self.status(cmd=cmd)

    def emergencyShutdown(self, cmd):
        self.stopCooler(cmd=cmd, forceShutdown=True)
    
    def errorFlags(self, errorMask):
        """Return a string describing the error state

        Args
        ----
        errorMask : `int`
          The device's error mask

        Returns
        -------
        errorMask : `int`
           The final errorMask. The input `errorMask` plus any synthetic bits
        errorString : `str`
           A human readable description of the final errorMask.

        Notes
        -----
       
        The documentation describes the following, but I suspect that there
        may be more...

        00000001 - High Reject Temperature
        00000010 - Low Reject Temperature 
        10000000 - Over Current Error 
        11111111 - Invalid Configuration

        In addition, we generate a synthetic error bit, bit 9,
        indicating that the reject temperature limit has ben exceeded.

        And a second synthetic bit, bit 10, indicating that the tip temp sensor
        is reading 400K.

        """

        bits = ('high reject temperature',
                'low reject temperature',
                'bit 2', 'bit 3', 'bit 4', 'bit 5', 'bit 6',
                'over current',
                'reject limit',
                'tip sensor disconnected')
        rejectBit = len(bits)-2
        rejectMask = 1 << rejectBit
        tipSensorBit = len(bits)-1
        tipSensorMask = 1 << tipSensorBit

        if self.rejectLimitHit:
            errorMask |= rejectMask
        if self.tipSensorBad:
            errorMask |= tipSensorMask
        if errorMask == 0:
            return errorMask, "OK"
        if (errorMask & 0xff == 0xff):
            elist = ["invalid configuration"]
            if errorMask & rejectMask:
                elist.append(bits[rejectBit])
            return errorMask, ', '.join(elist)

        elist = []
        for i in range(len(bits)):
            if errorMask & (1 << i):
                elist.append(bits[i])

        return errorMask, ', '.join(elist)
        
    def getTemps(self, cmd=None):
        mode = self.sendOneCommand('COOLER', doClose=False, cmd=cmd)
        errorMask = int(self.sendOneCommand('ERROR', doClose=False, cmd=cmd), base=2)
        try:
            maxPower = float(self.sendOneCommand('E', doClose=False, cmd=cmd, timeout=2))
            minPower = float(self.getOneResponse(cmd=cmd))
            power = float(self.getOneResponse(cmd=cmd))
        except ValueError:
            maxPower = np.nan
            minPower = np.nan
            power = np.nan
        tipTemp = float(self.sendOneCommand('TC', doClose=False, cmd=cmd))
        rejectTemp = float(self.sendOneCommand('TEMP2', doClose=False, cmd=cmd))
        setTemp = float(self.sendOneCommand('TTARGET', cmd=cmd))

        rejectLimit = self.actor.actorConfig[self.name]['rejectLimit']
        if rejectTemp > rejectLimit:
            self.stopCooler(cmd, forceShutdown=True)
        else:
            self.rejectLimitHit = False

        self.tipSensorBad = (tipTemp > 399)

        if cmd is not None:
            errorMask, errorString = self.errorFlags(errorMask)
            if errorString == 'OK':
                call = cmd.inform
            else:
                call = cmd.warn
            call('%sStatus=%s,0x%03x, %s, %g,%g,%g' % (self.name, mode,
                                                       errorMask, qstr(errorString),
                                                       minPower, maxPower, power))
            cmd.inform('%sTemps=%g,%g,%g, %g' % (self.name, setTemp,
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

