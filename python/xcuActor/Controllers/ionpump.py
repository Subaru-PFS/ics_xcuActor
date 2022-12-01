import logging
import socket
import time

import numpy as np

from opscore.utility.qstr import qstr
from functools import reduce

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

    def sendOneCommand(self, pumpIdx, cmdStr, cmd=None):
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
        cmd.diag('text="%s sending %s"' % (self.name, fullCmd))

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
        except socket.error as e:
            cmd.warn('text="failed to create socket to ion pump: %s"' % (e))
            raise

        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to ion pump: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from ion pump: %s"' % (e))
            raise

        self.logger.info('received %r', ret)
        cmd.diag('text="ionpump received %r"' % ret)
        s.close()

        reply = self.parseRawReply(ret)

        return reply

    def parseRawReply(self, raw):
        if len(raw) < 6:
            raise RuntimeError("too short reply: %r" % (raw))

        head = raw[:2]
        tail = raw[-3:]

        if head[:1] != b'\x02':
            raise RuntimeError("reply header is not x02: %r" % (raw))
        crc = self.calcCrc(raw[1:-2])
        wantTail = b'\x03%02X' % (crc)
        if tail != wantTail:
            raise RuntimeError("reply tail/crc is not %r: %r" % (wantTail,
                                                                 raw))

        return raw[2:-3]

    def sendReadCommand(self, pumpIdx, win, cmd=None):
        if isinstance(win, int):
            win = b"%03d" % (win)
        elif isinstance(win, str):
            win = win.encode('latin-1')

        reply = self.sendOneCommand(pumpIdx, win+b'0', cmd=cmd)

        if reply[:3] != win:
            raise RuntimeError("win in reply is not %s: %r" % (win,
                                                               reply))
        if reply[3:4] != b'0':
            raise RuntimeError("reply is not for a read: %r" % (reply))

        return reply[4:]

    def sendWriteCommand(self, pumpIdx, win, value, cmd=None):
        if isinstance(win, int):
            win = b"%03d" % (win)
        elif isinstance(win, str):
            win = win.encode('latin-1')

        reply = self.sendOneCommand(pumpIdx, win+b'1'+value.encode('latin-1'), cmd=cmd)

        return reply

    def readTemp(self, pumpIdx, cmd=None):
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
            reply = self.sendReadCommand(pumpIdx, win, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readVoltage(self, pumpIdx, cmd=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 800 + 10*channel, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readCurrent(self, pumpIdx, cmd=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 801 + 10*channel, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def readPressure(self, pumpIdx, cmd=None):
        _, channel = self.pumpAddrs[pumpIdx]
        try:
            reply = self.sendReadCommand(pumpIdx, 802 + 10*channel, cmd=cmd)
        except:
            reply = np.nan

        return float(reply)

    def _onOff(self, newState, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps on or off, and report the status. """

        graceTime = 2.0
        if newState:
            try:
                graceTime = self.actor.actorConfig[self.name]['delay']
            except:
                pass

        ret = []
        for pumpIdx, pumpAddr in enumerate(self.pumpAddrs):
            if pumpIdx == 0 and not pump1:
                continue
            if pumpIdx == 1 and not pump2:
                continue
            _, channel = pumpAddr

            retCmd = self.sendWriteCommand(pumpIdx, 10+channel,
                                           '%s' % (int(newState)), cmd=cmd)
            ret.append(retCmd)
            time.sleep(graceTime)

            self.startTimes[pumpIdx] = time.time()
            self.commandedOn[pumpIdx] = newState

        for pumpIdx, c in enumerate(self.pumpAddrs):
            self.readOnePump(pumpIdx, cmd=cmd)

        return ret

    def off(self, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps off, and report the status. """

        return self._onOff(False, pump1=pump1, pump2=pump2, cmd=cmd)

    def on(self, pump1=True, pump2=True, cmd=None):
        """ Turn the pumps on, and report the status. """

        return self._onOff(True, pump1=pump1, pump2=pump2, cmd=cmd)

    def readEnabled(self, pumpIdx, cmd=None):
        _, channel = self.pumpAddrs[pumpIdx]
        reply = self.sendReadCommand(pumpIdx, 10 + channel, cmd=cmd)
        return int(reply)

    def readError(self, pumpIdx, cmd=None):
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
        self.sendWriteCommand(pumpIdx, 505, '%06d' % (channel), cmd=cmd)
        reply = self.sendReadCommand(pumpIdx, 206, cmd=cmd)
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

    def readOnePump(self, pumpIdx, cmd=None):
        _, channel = self.pumpAddrs[pumpIdx]
        enabled = self.readEnabled(pumpIdx)

        V = self.readVoltage(pumpIdx, cmd=cmd)
        A = self.readCurrent(pumpIdx, cmd=cmd)
        p = self.readPressure(pumpIdx, cmd=cmd)
        t = self.readTemp(pumpIdx, cmd=cmd)

        err = self.readError(pumpIdx, cmd=cmd)

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
            self.off(cmd=cmd)

        return enabled,V,A,p
