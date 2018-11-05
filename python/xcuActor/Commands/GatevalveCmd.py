#!/usr/bin/env python

from builtins import object
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class GatevalveCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

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
            ('setLimits', '[<atm>] [<soft>] [<hard>]', self.setLimits),
            ('sam', 'off', self.samOff),
            ('sam', 'on', self.samOn),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gatevalve", (1, 1),
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
        
    def status(self, cmd, doFinish=True):
        """ Generate all gatevalve keys."""

        self.actor.controllers['gatevalve'].status(cmd=cmd)
        if doFinish:
            cmd.finish()

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
        
    def _checkOpenable(self, cmd, atAtmosphere, dPressLimitFlexible):
        try:
            pcm = self.actor.controllers['PCM']
        except KeyError:
            return 'PCM controller is not connected'
        
        try:
            pcm.powerOn('interlock')
        except Exception as e:
            return f'could not turn on interlock power: {e}'
        
        try:
            dewarPressure = pcm.pressure(cmd=cmd)
        except Exception as e:
            return f'could not check cryostat pressure: {e}'

        roughName = self.actor.roughName
        roughDict = self.actor.models[roughName].keyVarDict

        callVal = self.actor.cmdr.call(actor=roughName, cmdStr="gauge status", timeLim=3)
        if callVal.didFail:
            return 'failed to get roughing gauge pressure'
        
        callVal = self.actor.cmdr.call(actor=roughName, cmdStr="pump status", timeLim=3)
        if callVal.didFail:
            return 'failed to get roughing pump status'
        
        # Check what the invalid values are!!!! CPLXXX
        roughPressure = roughDict['pressure'].getValue()
        roughSpeed = roughDict['pumpSpeed'].getValue()
        roughMask, roughErrors = roughDict['pumpErrors'].getValue()
        
        if atAtmosphere:
            if dewarPressure < self.atmThreshold:
                return f'pressure too low to treat as atmosphere ({dewarPressure} < {self.atmThreshold})'

        dPress = abs(dewarPressure - roughPressure)
        if dPress >= self.dPressSoftLimit:
            if dPress >= self.dPressHardLimit:
                return f'pressure difference ({dPress}) exceeds hard limit ({self.dPressHardLimit})'
            if dPressLimitFlexible:
                cmd.warn(f'text="overriding pressure difference soft limit {self.dPressSoftLimit} with {dPress}"')
            else:
                return f'pressure difference ({dPress}) exceeds soft limit ({self.dPressSoftLimit})'

        return 'OK'

    def open(self, cmd):
        """ Enable gatevalve to be opened. Requires that |rough - dewar| <= 30 mTorr. 

        Either "atAtmosphere" or "underVacuum" must be specified. The tests applied are slightly
        different for the different modes:
         - underVacuum, the pumps must be on. 
        `- atAtmosphere, the pumps must be off.

        The hardware interlock might veto the action.
        """
        
        cmdKeys = cmd.cmd.keywords
        atAtmosphere = 'atAtmosphere' in cmdKeys
        underVacuum = 'underVacuum' in cmdKeys
        dryrun = 'dryrun' in cmdKeys
        argCheck = (atAtmosphere is True) ^ (underVacuum is True)
        if not argCheck:
            cmd.fail('text="either underVacuum or atAtmosphere must be set"')
        
        # Actively get rough and dewar side pressures
        status = self._checkOpenable(cmd, atAtmosphere, 'ok' in cmdKeys)
        
        if status != 'OK':
            if 'reallyforce' in cmdKeys:
                cmd.warn(f'text="gatevalve status is suspect but FORCEing it open ({status})"')
            else:
                cmd.fail(f'text="gatevalue opening blocked: {status}"')
                return

        if dryrun:
            cmd.finish('text="dryrun set, so not actually opening gatevalve"')
            return
        
        try:
            self.actor.controllers['gatevalve'].open(cmd=cmd)
        except Exception as e:
            cmd.fail('text="FAILED to open gatevalve!!"')
            return
        
        cmd.finish()
        
    def close(self, cmd):
        """ Close gatevalve. """

        self.actor.controllers['gatevalve'].close(cmd=cmd)
        cmd.finish()
        
    def samOff(self, cmd):
        """ Turn off SAM power. """

        self.actor.controllers['gatevalve'].powerOffSam(cmd=cmd)
        cmd.finish()
        
    def samOn(self, cmd):
        """ Turn off SAM power. """

        self.actor.controllers['gatevalve'].powerOnSam(cmd=cmd)
        cmd.finish()
        
