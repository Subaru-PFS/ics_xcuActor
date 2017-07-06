#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class GaugeCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('gauge', '@raw', self.pcmGaugeRaw),
            ('gauge', 'status', self.pcmPressure),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_roughgauge", (1, 1),
                                        keys.Key("query", types.Int(),
                                                 help='the MPT200 query'),
                                        )
        
    def gaugeRaw(self, cmd):
        """ Send a raw command to the roughGauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]
        ctrlr = cmd.cmd.name
        
        ret = self.actor.controllers[ctrlr].gaugeCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def gaugeQuery(self, cmd):
        """ Send a raw query to the roughGauge controller. """

        code = cmd.cmd.keywords['query'].values[0]
        ctrlr = cmd.cmd.name
        
        ret = self.actor.controllers[ctrlr].gaugeRawQuery(code, cmd=cmd)
        cmd.finish('text=%s' % (qstr("returned %s" % ret[10:-4])))

    def pressure(self, cmd):
        """ Fetch the latest pressure reading from a rough-side ion gauge. """
        
        ctrlr = cmd.cmd.name
        ret = self.actor.controllers[ctrlr].pressure(cmd=cmd)
        cmd.finish('roughPressure%s=%g' % (ctrlr[-1], ret))

    def pcmPressure(self, cmd):
        """ Fetch the latest pressure reading from the cryostat ion gauge. """

        ret = self.actor.controllers['PCM'].gaugeStatus(cmd=cmd)
        cmd.finish('pressure=%g' % (ret))
        
    def pcmGaugeRaw(self, cmd):
        """ Send a raw command to the PCM's gauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]
        
        ret = self.actor.controllers['PCM'].gaugeRawCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def pcmGaugeQuery(self, cmd):
        """ Send a raw query to the PCM's gauge controller. """

        code = cmd.cmd.keywords['code'].values[0]
        
        ret = self.actor.controllers['PCM'].gaugeCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))
