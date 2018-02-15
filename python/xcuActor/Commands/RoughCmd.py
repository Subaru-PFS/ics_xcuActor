#!/usr/bin/env python

from builtins import object
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

            ('roughGauge1', '@raw', self.gaugeRaw),
            ('roughGauge1', 'status', self.pressure),
            ('roughGauge1', '<setRaw>', self.setRaw),
            ('roughGauge1', '<getRaw>', self.getRaw),

            ('roughGauge2', '@raw', self.gaugeRaw),
            ('roughGauge2', 'status', self.pressure),
            ('roughGauge2', '<setRaw>', self.setRaw),
            ('roughGauge2', '<getRaw>', self.getRaw),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_rough", (1, 2),
                                        keys.Key("percent", types.Int(),
                                                 help='the speed for standby mode'),
                                        keys.Key("getRaw", types.Int(),
                                                 help='the MPT200 query'),
                                        keys.Key("setRaw",
                                                 types.CompoundValueType(types.Int(help='the MPT200 code'),
                                                                         types.String(help='the MPT200 value'))),
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

    def gaugeRaw(self, cmd):
        """ Send a raw command to a rough-side pressure gauge. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]
        ctrlr = cmd.cmd.name
        
        ret = self.actor.controllers[ctrlr].gaugeCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def getRaw(self, cmd):
        """ Send a direct query command to the PCM's gauge controller. """

        ctrlr = cmd.cmd.name
        cmdCode = cmd.cmd.keywords['getRaw'].values[0]
        
        ret = self.actor.controllers[ctrlr].gaugeRawQuery(cmdCode, cmd=cmd)
        cmd.finish('text=%s' % (qstr("returned %r" % ret)))

    def setRaw(self, cmd):
        """ Send a direct control command to the PCM's gauge controller. """

        ctrlr = cmd.cmd.name
        parts = cmd.cmd.keywords['setRaw'].values[0]
        cmdCode, cmdValue = parts

        cmd.diag('text="code=%r, value=%r"' % (cmdCode, cmdValue))
    
        ret = self.actor.controllers[ctrlr].gaugeRawSet(cmdCode, cmdValue, cmd=cmd)
        cmd.finish('text=%s' % (qstr("returned %r" % ret)))

    def pressure(self, cmd):
        """ Fetch the latest pressure reading from a rough-side pressure gauge. """
        
        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].pressure(cmd=cmd)
        cmd.finish('roughPressure%s=%g' % (ctrlr[-1], ret))

        
