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
            ('gatevalve', 'open (@force)', self.open),
            ('gatevalve', 'close', self.close),
            ('sam', 'off', self.samOff),
            ('sam', 'on', self.samOn),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gatevalve", (1, 1),
        )

    def status(self, cmd):
        """ Generate all gatevalve keys."""

        self.actor.controllers['gatevalve'].status(cmd=cmd)
        cmd.finish()

    def _checkOpenable(self, cmd):
        return 'unknown pressure differential'
    
    def open(self, cmd):
        """ Enable gatevalve to be opened. Requires that |rough - dewar| <= 30 mTorr. 

        The hardware interlock might veto the action.
        """
        cmdKeys = cmd.cmd.keywords

        # Actively get rough and dewar side pressures
        status = self._checkOpenable(cmd)

        if status != 'OK':
            if 'force' in cmdKeys:
                cmd.warn(f'text="gatevalve status is suspect ({status}), but FORCEing it open"')
            else:
                cmd.fail(f'text="gatevalue opening blocked: {status}"')
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
        
