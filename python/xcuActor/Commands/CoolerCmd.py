#!/usr/bin/env python

from builtins import object
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class CoolerCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.name = 'cooler'
        
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('cooler', '[<timeout>] raw', self.coolerRaw),
            ('cooler', 'status', self.status),
            ('cooler', 'temps', self.temps),
            ('cooler', 'on <setpoint>', self.tempLoop),
            ('cooler', 'power <setpoint>', self.powerLoop),
            ('cooler', 'off', self.off),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_cooler", (1, 2),
                                        keys.Key("setpoint", types.Float(),
                                                 help='cooler setpoint'),
                                        keys.Key("timeout", types.Float(),
                                                 help='timeout (in seconds) for raw command.'),
        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % (self.name))
    
    def coolerRaw(self, cmd):
        """ Send a raw command to the cryocooler controller. """

        cmdKeys = cmd.cmd.keywords
        timeout = cmdKeys['timeout'].values[0] if 'timeout' in cmdKeys else 1.0
        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        retLines = self.controller.rawCmd(cmd_txt, timeout=timeout, cmd=cmd)
        for line in retLines[:-1]:
            cmd.inform('text="returned %r"' % (line))
        cmd.finish('text="returned %r"' % (retLines[-1]))

    def status(self, cmd):
        """ Generate all cooler keys."""

        self.controller.status(cmd=cmd)
        cmd.finish()

    def temps(self, cmd):
        """ Generate temperature keys."""
        
        self.controller.getTemps(cmd=cmd)
        cmd.finish()

    def tempLoop(self, cmd):
        """ Turn cryocooler temperature control loop on. """

        setpoint = cmd.cmd.keywords['setpoint'].values[0]
        
        self.controller.startCooler('temp', setpoint, cmd=cmd)
        cmd.finish()
        
    def powerLoop(self, cmd):
        """ Turn cryocooler power control loop on. """

        setpoint = cmd.cmd.keywords['setpoint'].values[0]
        
        self.controller.startCooler('power', setpoint, cmd=cmd)
        cmd.finish()
        
    def off(self, cmd):
        """ Turn cryocooler control loop off. """

        self.controller.stopCooler(cmd=cmd)
        cmd.finish()
        
