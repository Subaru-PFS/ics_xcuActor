#!/usr/bin/env python

import logging
import time

import numpy as np

import opscore.protocols.keys as keys
import opscore.protocols.types as types

class GateValveState(object):
    OPEN_CMD = 1 << 7
    TURBO_AT_SPEED = 1 << 6
    PRESSURE_EQUAL = 1 << 5
    VACUUM_OK = 1 << 4
    GATEVALVE_OPEN = 1 << 3
    GATEVALVE_CLOSED = 1 << 2
    GATEVALVE_TIMEDOUT = 1 << 1
    GATEVALVE_SIGNAL = 1

    def __init__(self, state, gvMask=0x00, pressures=None):
        if isinstance(state, str):
            state = int(state, base=2)
        self.state = state
        if pressures is None:
            pressures = (np.nan, np.nan)
        self.setPressures(pressures)
        self.gvMask = gvMask

    def setPressures(self, pressures):
        self.outsidePressure = pressures[0]
        self.insidePressure = pressures[1]

    @property
    def position(self):
        """ Return the physical position of the gatevalve """

        if self.state & self.GATEVALVE_OPEN:
            if self.state & self.GATEVALVE_CLOSED:
                pos = "broken", "invalid"
            else:
                pos = "OK", "open"
        elif self.state & self.GATEVALVE_CLOSED:
            pos = "OK", "closed"
        else:
            pos = "OK", "unknown"

        return pos

    @property
    def request(self):
        if self.state & self.OPEN_CMD:
            if self.state & self.GATEVALVE_SIGNAL:
                pos = "OK", "open"
            elif self.state & self.GATEVALVE_TIMEDOUT:
                pos = "broken", "timedOut"
            else:
                pos = "blocked", "blocked"
        else:
            if not (self.state & self.GATEVALVE_SIGNAL):
                pos = "OK", "closed"
            else:
                pos = "broken", "impossible"

        return pos

    def isOpen(self):
        return ((self.state & self.GATEVALVE_OPEN)
                and not (self.state & self.GATEVALVE_CLOSED))

    def isClosed(self):
        return ((self.state & self.GATEVALVE_CLOSED)
                and not (self.state & self.GATEVALVE_OPEN))

    def isBlocked(self):
        return self.request[0] != "OK"

    def pressureDiff(self):
        """ Return the outside-inside pressure differernce. """
        return self.outsidePressure - self.insidePressure

    def describeBits(self):
        bits = []
        if self.state & self.OPEN_CMD:
            bits.append('open_cmd')
        if self.state & self.TURBO_AT_SPEED:
            bits.append('turbo_at_speed')
        if self.state & self.PRESSURE_EQUAL:
            bits.append('pressure_equal')
        if self.state & self.VACUUM_OK:
            bits.append('vacuum_ok')
        if self.state & self.GATEVALVE_OPEN:
            bits.append('gv_open')
        if self.state & self.GATEVALVE_CLOSED:
            bits.append('gv_closed')
        if self.state & self.GATEVALVE_TIMEDOUT:
            bits.append('gv_timeout')
        if self.state & self.GATEVALVE_SIGNAL:
            bits.append('gv_request')

        return ', '.join(bits)

    def getStateKey(self):
        stateKey = f'interlock={self.state:#08b},"{self.describeBits()}"'
        return stateKey

    def getPressureKey(self):
        pressureKey = f'interlockPressures={self.insidePressure:.2f},{self.outsidePressure:.2f}'
        return pressureKey

    def getGatevalveKey(self):
        """ Historical key, before we could know _why_ the GV could be blocked. """

        stateKey = f'gatevalve={self.state:#02x},{self.position[-1]},{self.request[-1]}; gvMask={self.gvMask:#02x}'
        return stateKey

    def getStateKeys(self):
        return ';'.join([self.getGatevalveKey(), self.getStateKey()])

    def getAllKeys(self):
        return ';'.join([self.getPressureKey(), self.getGatevalveKey(), self.getStateKey()])

class GatevalveCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.logger = logging.getLogger('gatevalve')

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('gatevalve', 'status', self.status),
            ('gatevalve', 'open [@(underVacuum)] [@(atAtmosphere)] [@(ok)] [@(reallyforce)] [@(dryrun)]',
             self.open),
            ('gatevalve', 'close', self.close),
            ('interlock', 'status', self.status),
            ('interlock', '@raw', self.interlockRaw),
            ('interlock', 'sendImage <path> [@doWait] [@sendReboot] [@straightToCode]', self.sendImage),
            ('setLimits', '[<atm>] [<soft>] [<hard>]', self.setLimits),
            ('sam', 'status', self.samStatus),
            ('sam', 'off', self.samOff),
            ('sam', 'on', self.samOn),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gatevalve", (1, 2),
                                        keys.Key("path", types.String(),
                                                 help='path of firmware file'),
                                        keys.Key("soft", types.Float(),
                                                 help='soft limit for dPressure'),
                                        keys.Key("atm", types.Float(),
                                                 help='lower limit for atmospheric pressure'),
                                        keys.Key("hard", types.Float(),
                                                 help='hard limit for dPressure'),
        )

        # The valve manual declares 30 mbar/22.5 Torr as the maximum pressure across the valve.
        self.atmThreshold = 460.0  # The absolute lowest air pressure to accept as at atmosphere, Torr
        self.dPressSoftLimit = 22  # The overridable pressure difference limit for opening, Torr
        self.dPressHardLimit = 22  # The absolute pressure difference limit for opening, Torr

        rougher = self.roughName

    @property
    def roughName(self):
        sm = self.actor.ids.idDict['spectrograph']
        if sm in {1, 2}:
            roughName = 'rough1'
        else:
            roughName = 'rough2'

        try:
            roughOverride = self.actor.actorConfig.get('roughActor', None)
            if roughOverride is not None:
                logging.warning('overwriting default roughActor with %s',
                                roughOverride)
                roughName = roughOverride
        except:
            pass

        try:
            self.actor.actorConfig['interlock']['ignoreRoughPump']
            roughName = None
            logging.warning('ignoring roughing pump')
        except Exception:
            pass

        if roughName is not None and roughName not in self.actor.models:
            self.actor.addModels([roughName])
        return roughName

    @property
    def interlock(self):
        return self.actor.controllers['interlock']

    @property
    def gatevalve(self):
        return self.actor.controllers['gatevalve']

    def interlockRaw(self, cmd):
        """ Send a raw command to the interlock controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.interlock.sendCommandStr(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def sendImage(self, cmd):
        """ Upload new firmware to interlock board. """

        cmdKeys = cmd.cmd.keywords
        path = cmdKeys['path'].values[0]
        doWait = 'doWait' in cmdKeys
        sendReboot = 'sendReboot' in cmdKeys
        straightToCode = 'straightToCode' in cmdKeys

        self.interlock.sendImage(path, verbose=True, doWait=doWait,
                                 sendReboot=sendReboot,
                                 straightToCode=straightToCode, cmd=cmd)
        cmd.finish()

    def status(self, cmd, doFinish=True):
        """ Generate all gatevalve keys."""

        cmd.inform(f'roughActor={self.roughName}')
        self._doStatus(cmd, doFinish=doFinish)

    def setLimits(self, cmd):
        """(Engineering) set soft and hard dPressures, minimum atmPressure """
        cmdKeys = cmd.cmd.keywords

        if 'soft' in cmdKeys:
            self.dPressSoftLimit = cmdKeys['soft'].values[0]
        if 'hard' in cmdKeys:
            self.dPressHardLimit = cmdKeys['hard'].values[0]
        if 'atm' in cmdKeys:
            self.atmThreshold = cmdKeys['atm'].values[0]

        if self.dPressSoftLimit > self.dPressHardLimit:
            self.dPressSoftLimit = self.dPressHardLimit

        cmd.finish(f'text="dPressure limits are atm={self.atmThreshold} soft={self.dPressSoftLimit} hard={self.dPressHardLimit}"')

    def _getDewarPressure(self, cmd):
        state = self.interlockStatus(cmd)
        dewarPressure = state.insidePressure

        return dewarPressure

    def _getRoughPressure(self, cmd):
        state = self.interlockStatus(cmd)
        roughPressure = state.outsidePressure

        return roughPressure

    def _checkOpenable(self, cmd, atAtmosphere, dPressLimitFlexible):
        """ Check whether the gatevalve can be opened.

        Returns
        -------

        errorString : str
          "OK" if the valve can be opened, a useful striung otherwise.

        """

        try:
            pcm = self.actor.controllers['PCM']
        except KeyError:
            return 'PCM controller is not connected'

        powerMaskRaw = pcm.pcmCmd('~ge')
        powerMask = int(powerMaskRaw[2:], base=2)
        if not pcm.systemInPowerMask(powerMask, 'interlock'):
            return 'interlock board not powered up (by PCM)',

        dewarPressure = self._getDewarPressure(cmd)

        roughName = self.roughName
        if roughName is None:
            roughPressure = self._getRoughPressure(cmd)
            roughSpeed = -9999
        else:
            roughDict = self.actor.models[roughName].keyVarDict
            callVal = self.actor.cmdr.call(actor=roughName, cmdStr="gauge status", timeLim=3)
            if callVal.didFail:
                return 'failed to get roughing gauge pressure',

            callVal = self.actor.cmdr.call(actor=roughName, cmdStr="pump status", timeLim=3)
            if callVal.didFail:
                return 'failed to get roughing pump status',

            # Check what the invalid values are!!!! CPLXXX
            roughSpeed = roughDict['pumpSpeed'].getValue()
            roughMask, roughErrors = roughDict['pumpErrors'].getValue()
            roughPressure = self._getRoughPressure(cmd)

        turboSpeed, turboStatus = self.actor.controllers['turbo'].speed(cmd)
        # turboDict = self.actor.models[self.actor.name].keyVarDict


        problems = []
        if atAtmosphere:
            if roughName is not None and roughSpeed > 0:
                problems.append(f'roughing pump cannot be on to open at atmosphere')
            if turboSpeed > 0:
                problems.append(f'turbo pump cannot be on to open at atmosphere')
            if dewarPressure < self.atmThreshold:
                problems.append(f'dewar pressure too low to treat as atmosphere ({dewarPressure} < {self.atmThreshold})')
            if roughPressure < self.atmThreshold:
                problems.append(f'roughing pressure too low to treat as atmosphere ({roughPressure} < {self.atmThreshold})')
        else:
            if roughName is not None and roughSpeed < 30:
                problems.append(f'roughing pump must be at speed to open under vacuum')
            if turboSpeed < 90000:
                problems.append(f'turbo pump must be at speed to open under vacuum')
            if dewarPressure >= self.atmThreshold:
                problems.append(f'dewar pressure too high to treat as vacuum ({dewarPressure} >= {self.atmThreshold})')
            if roughPressure >= self.atmThreshold:
                problems.append(f'roughing pressure too high to treat as vacuum ({roughPressure} >= {self.atmThreshold})')

        dPress = abs(dewarPressure - roughPressure)
        if dPress >= self.dPressSoftLimit:
            if dPress >= self.dPressHardLimit:
                problems.append(f'pressure difference ({dPress}) exceeds hard limit ({self.dPressHardLimit})')
            if dPressLimitFlexible:
                cmd.warn(f'text="overriding pressure difference soft limit {self.dPressSoftLimit} with {dPress}"')
            else:
                problems.append(f'pressure difference ({dPress}) exceeds soft limit ({self.dPressSoftLimit})')

        if len(problems) == 0:
            return 'OK'
        else:
            return problems

    def open(self, cmd):
        """ Enable gatevalve to be opened. Requires that |rough - dewar| <= 22 Torr.

        Either "atAtmosphere" or "underVacuum" must be specified. The tests applied are slightly
        different for the different modes. Mainly:
         - underVacuum, the pumps must be on.
        `- atAtmosphere, the pumps must be off.

        If "dryrun" is passed in, all tests will be made, but if the valve can be opened it will not be.

        If "reallyforce" is passed in, then the valve motion will be enabled regardless of any
        failed safety tests. Any detector damage is on you.

        The hardware interlock might veto the action.
        """

        cmdKeys = cmd.cmd.keywords
        atAtmosphere = 'atAtmosphere' in cmdKeys
        underVacuum = 'underVacuum' in cmdKeys
        dryrun = 'dryrun' in cmdKeys
        argCheck = atAtmosphere ^ underVacuum
        if not argCheck:
            cmd.fail('text="either underVacuum or atAtmosphere must be set"')
            return

        # Actively get rough and dewar side pressures
        status = self._checkOpenable(cmd, atAtmosphere, 'ok' in cmdKeys)

        if status != 'OK':
            if 'reallyforce' in cmdKeys:
                for problem in status:
                    cmd.warn(f'text="gatevalve opening WOULD be blocked: {problem}')
                cmd.warn(f'text="gatevalve status is suspect but FORCEing it open"')
            else:
                for problem in status:
                    cmd.warn(f'text="gatevalve opening blocked: {problem}')
                cmd.fail(f'text="gatevalue was NOT opened"')
                return

        if dryrun:
            cmd.finish('text="dryrun set, so not actually opening gatevalve"')
            return

        self._doOpen(cmd=cmd)

    def close(self, cmd):
        """ Close gatevalve. """

        self._doClose(cmd=cmd)

    def _spinUntil(self, testFunc, starting=None, timeLimit=2.0, cmd=None):
        """ Poll interlock state until success or timeout. """

        pause = 0.2
        lastState = starting
        while timeLimit > 0:
            ret = self.getGatevalveStatus(cmd, silentIf=lastState)
            if testFunc(ret):
                return ret
            lastState = ret.state
            timeLimit -= pause
            time.sleep(pause)
        cmd.warn(f"failed to get desired gate valve state. Timed out with: {ret.state:#08b})")
        raise RuntimeError()

    def _doOpen(self, cmd):
        state = self._doStatus(cmd, doFinish=False)
        if state.isBlocked():
            cmd.fail('text="gatevalve open command is blocked. Close it to re-enable opening"')
            return

        def isOpen(status):
            return status.isOpen()

        try:
            self.gatevalve.request(True)
            self._spinUntil(isOpen, cmd=cmd)
        except Exception as e:
            # cmd.warn(f'text="FAILED to open gatevalve: {e} -- commanding it to close"')
            self._doStatus(cmd)
            # self._doClose(cmd=cmd, doFinish=False)
            cmd.fail(f'text="FAILED to open gatevalve; close it to re-enable opening"')
            return

        self._doStatus(cmd)
        cmd.finish()

    def _doClose(self, cmd, doFinish=True):
        def isClosed(status):
            return status.isClosed()

        try:
            self.gatevalve.request(False)
            self._spinUntil(isClosed, cmd=cmd)
        except Exception as e:
            cmd.fail(f'text="FAILED to close gatevalve!!!!! {e}"')
            return

        self._doStatus(cmd)
        if doFinish:
            cmd.finish()

    def _doStatus(self, cmd, doFinish=True):
        ret = self.interlockStatus(cmd)

        if doFinish:
            cmd.finish()

        return ret

    def getGatevalveStatus(self, cmd, silentIf=None):
        """ Get status from the new interlock board. """

        rawStatus = self.interlock.sendCommandStr('gStat,all', cmd=cmd)
        gvMask = self.gatevalve.getStatus()
        state = GateValveState(rawStatus, gvMask=gvMask)

        if silentIf is not True and state.state != silentIf:
            cmd.inform(state.getStateKeys())
        return state

    def interlockStatus(self, cmd):
        """ Get status from the new interlock board. """

        state = self.getGatevalveStatus(cmd, silentIf=True)

        # The new board returns pressures in mbar. The rest of the instrument uses Torr.
        # Convert here.
        pressuresRaw = self.interlock.sendCommandStr('gP,all', cmd=cmd)
        pressures = [0.75*float(s) for s in pressuresRaw.split(',')]
        if any([p <= -10 for p in pressures]):
            cmd.warn('text="raw interlock board pressures are suspiciously low: %s"' % (pressures))
        pressures = [max(p, 0.0) for p in pressures]

        state.setPressures(pressures)
        cmd.inform(state.getAllKeys())

        return state

    def samStatus(self, cmd, doFinish=True):
        """ Report SAM power. """

        samStatus = self.gatevalve.samStatus()
        resp = f'sampower={int(samStatus)}'
        if doFinish:
            cmd.finish(resp)
        else:
            cmd.inform(resp)

    def samOff(self, cmd):
        """ Turn off SAM power. """

        self.samStatus(cmd=cmd, doFinish=False)
        self.gatevalve.powerOffSam(cmd=cmd)
        self.samStatus(cmd=cmd)

    def samOn(self, cmd):
        """ Turn off SAM power. """

        self.samStatus(cmd=cmd, doFinish=False)
        self.gatevalve.powerOnSam(cmd=cmd)
        self.samStatus(cmd=cmd)
