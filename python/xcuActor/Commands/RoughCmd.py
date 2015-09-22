#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class RoughCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('rough1', '@raw', self.roughRaw),
            ('rough1', 'ident', self.ident),
            ('rough1', 'status', self.status),
            ('rough1', 'start', self.startRough),
            ('rough1', 'stop', self.stopRough),
            ('rough1', 'standby <percent>', self.standby),
            ('rough1', 'standby off', self.standbyOff),

            ('rough2', '@raw', self.roughRaw),
            ('rough2 ident', '', self.ident),
            ('rough2 status', '', self.status),
            ('rough2 start', '', self.startRough),
            ('rough2 stop', '', self.stopRough),
            ('rough2 standby', '<percent>', self.standby),
            ('rough2 standby', 'off', self.standbyOff),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_rough", (1, 1),
                                        keys.Key("percent", types.Int(),
                                                 help='the speed for standby mode'),
                                        )

    def roughRaw(self, cmd):
        """ Send a raw command to the rough controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['rough'].pumpCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ident(self, cmd):
        """ Return the rough ids. 

         - the rough model
         - DSP software version
         - PIC software version
         - full speed in RPM
         
        """
        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].ident(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def status(self, cmd):
        """ Return all status keywords. """
        ctrlr = cmd.cmd.name
        self.actor.controllers[ctrlr].status(cmd=cmd)
        cmd.finish()

    def standby(self, cmd):
        """ Go into standby mode, where the pump runs at a lower speed than normal. """
        
        ctrlr = cmd.cmd.name
        percent = cmd.cmd.keywords['percent'].values[0]
        ret = self.actor.controllers[ctrlr].startStandby(percent=percent,
                                                         cmd=cmd)
        cmd.finish('text=%r' % (qstr(ret)))

    def standbyOff(self, cmd):
        """ Drop out of standby mode and go back to full-speed."""
        
        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].stopStandby(cmd=cmd)
            
        cmd.finish('text=%r' % (qstr(ret)))

    def startRough(self, cmd):
        """ Turn on roughing pump. """
        
        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].startPump(cmd=cmd)
        cmd.finish('text=%s' % (','.join(ret)))

    def stopRough(self, cmd):
        """ Turn off roughing pump. """

        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].stopPump(cmd=cmd)
        cmd.finish('text=%s' % (','.join(ret)))
