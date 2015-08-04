#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TurboCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('turbo', '@raw', self.turboRaw),
            ('turbo', 'ident', self.ident),
            ('turbo', 'monitor <period>', self.monitor),
            ('turbo', 'status', self.status),
            ('turbo', 'start', self.startTurbo),
            ('turbo', 'stop', self.stopTurbo),
            ('turbo', 'standby <percent>', self.standby),
            ('turbo', 'standby off', self.standby),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_turbo", (1, 1),
                                        keys.Key("percent", types.Int(),
                                                 help='the speed for standby mode'),
                                        keys.Key("period", types.Int(),
                                                 help='how often to poll for status'),

                                        )

    def turboRaw(self, cmd):
        """ Send a raw command to the turbo controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['turbo'].turboCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ident(self, cmd):
        """ Return the turbo ids. 

         - the turbo model
         - DSP software version
         - PIC software version
         - full speed in RPM
         
        """
        ret = self.actor.controllers['turbo'].ident(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def status(self, cmd):
        self.actor.controllers['turbo'].status(cmd=cmd)
        cmd.finish()

    def monitor(self, cmd):
        period = cmd.cmd.keywords['period'].values[0]
        self.actor.monitorTurbo(period)
        cmd.finish()
        
    def standby(self, cmd):
        if 'percent' in cmd.cmd.keywords:
            percent = cmd.cmd.keywords['percent'].values[0]
            ret = self.actor.controllers['turbo'].startStandby(percent=percent,
                                                              cmd=cmd)
        else:
            ret = self.actor.controllers['turbo'].stopStandby(cmd=cmd)
            
        cmd.finish('text=%r' % (qstr(ret)))

    def startTurbo(self, cmd):
        ret = self.actor.controllers['turbo'].startTurbo(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def stopTurbo(self, cmd):
        ret = self.actor.controllers['turbo'].stopTurbo(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))
