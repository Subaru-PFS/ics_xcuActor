import logging
import socket
import time
import traceback

import numpy as np

from opscore.utility.qstr import qstr
from functools import reduce

class IncompleteReply(Exception):
    pass

class ConnectTo4UHV:
    """
    Provide a context manager around a connction to a 4UHV.

    Adds two features to a normal socket:

    - retries failed connections. We *do* have contention at the far
    end: allow other clients to finish.

    - allows reuse of existing connection.
    """
    def __init__(self, cmd, host, port, sock=None, tryFor=3.0, waitTime=0.25):
        self.cmd = cmd
        self.host = host
        self.port = port
        self.sock = sock
        self.doClose = sock is None
        self.tryFor = tryFor
        self.waitTime = waitTime

    def __enter__(self):
        cmd = self.cmd
        if self.sock is not None:
            # cmd.debug(f'text="keeping given socket: {self.sock}"')
            return self.sock

        try:
            self.sock = sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.waitTime)
        except socket.error as e:
            cmd.warn('text="failed to create socket to ion pump: %s"' % (e))
            raise

        tryFor = self.tryFor
        while tryFor > 0:
            try:
                cmd.debug(f'text="connecting {sock} to ({self.host}:{self.port}) ({tryFor}s left)"')
                sock.connect((self.host, self.port))
                sock.settimeout(1.0)
                return sock
            except socket.error as e:
                tryFor -= self.waitTime
                if tryFor > 0:
                    cmd.debug(f'text="failed to connect to ion pump; retrying {tryFor} ({e})"')
                    time.sleep(self.waitTime)
                else:
                    cmd.warn('text="failed to connect to ion pump: %s"' % (e))
                    raise

        cmd.warn(f'text="failed to connect to ion pump within {tryFor}s"')
        raise RuntimeError(f'failed to connect to ion pump within {tryFor}s')

    def __exit__(self, exc_type, exc_value, exc_tb):
        cmd = self.cmd
        if self.doClose:
            try:
                cmd.debug(f'text="closing {self.sock}"')
                self.sock.close()
            except Exception as e:
                cmd.warn(f'text="failed to close ionpump: {e}"')

        if exc_type is not None:
            tb0 = traceback.extract_tb(exc_tb)[-1]
            cmd.warn(f'text="error commanding ionpump at {tb0.filename}:{tb0.lineno} -- {exc_type.__name__}: {exc_value}"')
            return True

class ionpump(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = b'\r'

        self.host = self.actor.actorConfig[self.name]['host']
        self.port = self.actor.actorConfig[self.name]['port']

        # Try getting new INSTRM-XXXX pair of busIds first, then
        # use historical single value.
        # Internally, we carry a pair of (4UHV_addr, channel_addr) pairs
        try:
            busIds = self.actor.actorConfig[self.name]['busIds']
        except KeyError:
            busId = self.actor.actorConfig[self.name]['busId']
            busIds = [busId, busId]

        pumpIds = self.actor.actorConfig[self.name]['pumpIds']
        self.pumpAddrs = ((busIds[0], pumpIds[0]),
                          (busIds[1], pumpIds[1]))
        self.startTimes = [0, 0]
        self.commandedOn = [None, None]

        self.logger.info(f'text="ionpump {self.host}:{self.port} {self.pumpAddrs}"')

    def __str__(self):
        a = self.pumpAddrs
        return f'ionpumps({self.host}:{self.port}; pump1:{a[0]}; pump2:{a[1]})'

    @property
    def npumps(self):
        return len(self.pumpAddrs)

    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        pass

    def calcCrc(self, s):
        crc = reduce(int.__xor__, [c for c in s])
        return crc

    def valueType(self, win):
        """Return the value type for a given window.

        See the Window Protocol sectoin of the fine manual.
        """

        if win in {11, 12, 13, 14, 504}:
            return bool
        elif win in {602, 603, 615, 625, 635, 645}:
            return int
        else:
            return str
        
    def readOneReply(self, cmd, sock) -> str:
        # Try to consume a full reply, which might (unlikely but possible)
        # come in 2+ packets.
        ntries = 10
        i = 0
        ret = b''
        while i < ntries:
            try:
                ret1 = sock.recv(1024)
            except socket.error as e:
                cmd.warn('text="failed to read response from ion pump: %s"' % (e))
                raise

            self.logger.info('received %r', ret1)
            cmd.diag('text="ionpump received %r"' % ret1)
            ret += ret1

            try:
                reply = self.parseRawReply(ret, cmd)
                if i > 0:
                    cmd.diag(f'text="ionpump received complete response: {reply}"')
                return reply
            except IncompleteReply:
                cmd.warn(f'text="ionpump received partial response ({ret}/{ret1}) {i+1}/{ntries}"')
                i += 1
                time.sleep(0.01)
            except Exception as e:
                cmd.warn('text="failed to read complete response from ion pump: %s"' % (e))
                raise
        cmd.warn(f'text="timed out reading response from ion pump; have {ret}"')
        raise RuntimeError("timed out reading response from ion pump")

    def sendOneCommand(self, pumpIdx, cmdStr, sock=None, cmd=None) -> str:
        """Send a single atomic ionpump command and return the response.

        Args
        ----
        pumpIdx : `int`
            the internal index of the ionpump. 0 or 1
        cmdStr : `str` or `bytes`
            the register read/write part of the command. We
            add the CRC, etc.
        sock : `socket.socket`
            if passed in, use this. Else make a new connection.
        cmd : `Command`
            what to send errors and progress diagnostics to.

        Returns
        -------
        reply : `bytes`
            the content of the command response
        """

        if cmd is None:
            cmd = self.actor.bcast

        try:
            cmdStr = cmdStr.encode('latin-1')
        except AttributeError:
            pass

        busAddr, _ = self.pumpAddrs[pumpIdx]
        busID = bytes([128 + int(busAddr)])
        coreCmd = b"%s%s\x03" % (busID, cmdStr)
        crc = self.calcCrc(coreCmd)
        fullCmd = b"\x02%s%02X" % (coreCmd, crc)
        self.logger.info('sending %r to %s:%s:%s', fullCmd, self.host, self.port, busAddr)

        with ConnectTo4UHV(cmd=cmd, host=self.host, port=self.port, sock=sock) as sock:
            cmd.diag('text="%s sending %s"' % (self.name, fullCmd))
            try:
                sock.sendall(fullCmd)
            except socket.error as e:
                cmd.warn('text="failed to send command to ion pump: %s"' % (e))
                raise

            return self.readOneReply(cmd, sock)

    def parseRawReply(self, raw, cmd):
        if len(raw) < 6:
            cmd.warn(f'text="reply too short {raw}"')
            raise IncompleteReply("too short reply: %r" % (raw))

        head = raw[:2]
        tail = raw[-3:]

        if head[:1] != b'\x02':
            raise RuntimeError("reply header is not x02: %r" % (raw))
        if tail[:1] != b'\x03':
            cmd.warn(f'text="reply too short? {tail} {tail[0]}"')
            raise IncompleteReply("probably too short reply: %r" % (raw))

        crc = self.calcCrc(raw[1:-2])
        wantTail = b'\x03%02X' % (crc)
        if tail != wantTail:
            cmd.warn(f'text="reply corrupt? {tail} vs. {wantTail}"')
            raise RuntimeError("reply tail/crc is not %r: %r" % (wantTail,
                                                                 raw))
        return raw[2:-3]

    def sendReadCommand(self, pumpIdx, win, cmd=None, sock=None):
        if not isinstance(win, int):
            raise RuntimeError("win must be an int: %s=%r" % (type(win), win))
        win = b"%03d" % (win)

        reply = self.sendOneCommand(pumpIdx, win+b'0',
                                    sock=sock, cmd=cmd)
        if not reply:
            raise RuntimeError("no reply to read command of %s: %r" % (win,
                                                                       reply))
        if reply[:3] != win:
            raise RuntimeError("win in reply is not %s: %r" % (win,
                                                               reply))
        if reply[3:4] != b'0':
            raise RuntimeError("reply is not for a read: %r" % (reply))

        return reply[4:]

    def sendWriteCommand(self, pumpIdx, win, value, cmd=None, sock=None):
        if not isinstance(win, int):
            raise RuntimeError("win must be an int: %s=%r" % (type(win), win))
        win = b"%03d" % (win)

        reply = self.sendOneCommand(pumpIdx, win+b'1'+value.encode('latin-1'),
                                    sock=sock, cmd=cmd)
        return reply

    def readTemp(self, pumpIdx, cmd=None, sock=None):
        _, channel = self.pumpAddrs[pumpIdx]

        if channel == 1:
            win = 801
        elif channel == 2:
            win = 802
        elif channel == 3:
            win = 808
        elif channel == 4:
            win = 809
        else:
            raise RuntimeError("unknown channel %s" % (channel))

        try:
            reply = self.sendReadCommand(pumpIdx, win,
                                         sock=sock, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readVoltage(self, pumpIdx, cmd=None, sock=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 800 + 10*channel,
                                         sock=sock, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readCurrent(self, pumpIdx, cmd=None, sock=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 801 + 10*channel,
                                         sock=sock, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readPressure(self, pumpIdx, cmd=None, sock=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 802 + 10*channel,
                                         sock=sock, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def _onOff(self, newState, pump1=True, pump2=True, cmd=None, sock=None):
        """ Turn the pumps on or off, and report the status. """

        graceTime = 2.0
        if newState:
            try:
                graceTime = self.actor.actorConfig[self.name]['delay']
            except:
                pass

        with ConnectTo4UHV(cmd=cmd, host=self.host, port=self.port, sock=sock) as sock:
            ret = []
            for pumpIdx, pumpAddr in enumerate(self.pumpAddrs):
                if pumpIdx == 0 and not pump1:
                    continue
                if pumpIdx == 1 and not pump2:
                    continue
                _, channel = pumpAddr

                retCmd = self.sendWriteCommand(pumpIdx, 10+channel,
                                               '%s' % (int(newState)),
                                               sock=sock, cmd=cmd)
                ret.append(retCmd)

                self.startTimes[pumpIdx] = time.time()
                self.commandedOn[pumpIdx] = newState

            time.sleep(graceTime)
            for pumpIdx, c in enumerate(self.pumpAddrs):
                self.readOnePump(pumpIdx, sock=sock, cmd=cmd)

        return ret

    def off(self, pump1=True, pump2=True, cmd=None, sock=None):
        """ Turn the pumps off, and report the status. """

        return self._onOff(False, pump1=pump1, pump2=pump2,
                           cmd=cmd, sock=sock)

    def on(self, pump1=True, pump2=True, cmd=None, sock=None):
        """ Turn the pumps on, and report the status. """

        return self._onOff(True, pump1=pump1, pump2=pump2,
                           cmd=cmd, sock=sock)

    def readEnabled(self, pumpIdx, cmd=None, sock=None):
        _, channel = self.pumpAddrs[pumpIdx]
        reply = self.sendReadCommand(pumpIdx, 10 + channel,
                                     sock=sock, cmd=cmd)
        return int(reply)

    def readError(self, pumpIdx, cmd=None, sock=None):
        """ Read the error mask for a single channel, or the union of all. 

        Args
        ----
        channel - int
          1-4 for an individual channel, or 0 for the OR of all

        Returns
        -------
        mask - the errors as detailed in Table 13 of the 4UHV manual.
        """
        _, channel = self.pumpAddrs[pumpIdx]
        self.sendWriteCommand(pumpIdx, 505, '%06d' % (channel),
                              sock=sock, cmd=cmd)
        reply = self.sendReadCommand(pumpIdx, 206,
                                     sock=sock, cmd=cmd)
        return int(reply)

    errorBits = {0x0001:"Fan error",
                 0x0002:"HV power input error",
                 0x0004:"PFC power input error",
                 0x0008:"PFC overtemp",
                 0x0010:"CPU-HV communication error",
                 0x0020:"Interlock cable",
                 0x0040:"HV overtemp",
                 0x0080:"Protection error",
                 0x0100:"Measurement error",
                 0x0200:"HV output error",
                 0x0400:"Short circuit",
                 0x0800:"HV disabled",
                 0x1000:"0x1000",
                 0x2000:"0x2000",
                 0x4000:"0x4000",

                 # And our synthetic bits:
                 0x8000:"Channel enabled but no current/voltage/pressure",
                 0x10000:"Pressure limit hit",
                 0x20000:"Pump shut down by itself"}
    
    def _makeErrorString(self, err):
        """ Return a string describing all error bits, or 'OK'. """

        if err == 0:
            return "OK"
        errors = []
        for i in range(len(self.errorBits)):
            mask = 1 << i
            if err & mask:
                errors.append(self.errorBits[mask])

        return ",".join(errors)

    def readOnePump(self, pumpIdx, sock=None, cmd=None):
        with ConnectTo4UHV(cmd=cmd, host=self.host, port=self.port, sock=sock) as sock:
            enabled = self.readEnabled(pumpIdx, sock=sock)

            V = self.readVoltage(pumpIdx, cmd=cmd, sock=sock)
            A = self.readCurrent(pumpIdx, cmd=cmd, sock=sock)
            p = self.readPressure(pumpIdx, cmd=cmd, sock=sock)
            t = self.readTemp(pumpIdx, cmd=cmd, sock=sock)

            err = self.readError(pumpIdx, cmd=cmd, sock=sock)

            # INSTRM-594, INSTRM-758: create synthetic error when pump is on but not indicating current or pressure.
            doTurnOff = False
            if enabled and (V == 0 or A == 0 or p == 0):
                err |= 0x8000
                doTurnOff = True

            # INSTRM-772: create synthetic error when high pressure limit hit
            if (enabled and
                (time.time() - self.startTimes[pumpIdx] > self.actor.actorConfig[self.name]['spikeDelay']) and
                (p > self.actor.actorConfig[self.name]['maxPressure'])):

                err |= 0x10000
                doTurnOff = True

            if (enabled and
                (time.time() - self.startTimes[pumpIdx] < self.actor.actorConfig[self.name]['spikeDelay']) and
                (p > self.actor.actorConfig[self.name]['maxPressureDuringStartup'])):

                err |= 0x10000
                doTurnOff = True

            # INSTRM-1150: create synthetic error when pumps shut down on their own.
            if self.commandedOn[pumpIdx] is True and not enabled:
                err |= 0x20000
                self.commandedOn[pumpIdx] = False
            # If the actor has restarted, set our commandedOn state to the controller's state.
            if self.commandedOn[pumpIdx] is None:
                self.commandedOn[pumpIdx] = enabled

            if cmd is not None:
                cmdFunc = cmd.inform if err == 0 else cmd.warn
                errString = self._makeErrorString(err)

                cmdFunc('ionPump%d=%d,%g,%g,%g, %g' % (pumpIdx+1,
                                                       enabled,
                                                       V,A,t,p))
                cmdFunc('ionPump%dErrors=0x%05x,%s,%s' % (pumpIdx+1, err,
                                                          "OK" if errString == "OK" else "ERROR",
                                                          qstr(errString)))
            if doTurnOff:
                # Just turn off a single pump
                self.off(cmd=cmd, sock=sock,
                         pump1=(pumpIdx==0), pump2=(pumpIdx==1))

            return enabled,V,A,p
