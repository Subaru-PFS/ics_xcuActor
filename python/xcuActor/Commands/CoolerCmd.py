#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class CoolerCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('cooler', '@raw', self.coolerRaw),
            ('cooler', 'status', self.status),
            ('cooler', 'temps', self.temps),
            ('cooler', 'on <setpoint>', self.on),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_cooler", (1, 1),
                                        keys.Key("setpoint", types.Float(),
                                                 help='cooler setpoint'),
                                        
        )

    def coolerRaw(self, cmd):
        """ Send a raw command to the cooler controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['cooler'].rawCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def status(self, cmd):
        self.actor.controllers['cooler'].status(cmd=cmd)
        cmd.finish()

    def temps(self, cmd):
        self.actor.controllers['cooler'].getTemps(cmd=cmd)
        cmd.finish()

    def on(self, cmd):
        setpoint = cmd.cmd.keywords['setpoint'].values[0]
        
        self.actor.controllers['cooler'].startCooler(setpoint, cmd=cmd)
        cmd.finish()
        
