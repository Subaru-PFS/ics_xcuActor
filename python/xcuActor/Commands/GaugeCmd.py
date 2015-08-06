#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
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
            ('gauge', '@raw', self.gaugeRaw),
            ('gauge', 'status', self.pressure),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gauge", (1, 1),
                                        )

    def gaugeRaw(self, cmd):
        """ Send a raw command to the gauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['gauge'].gaugeCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def pressure(self, cmd):
        ret = self.actor.controllers['gauge'].pressure(cmd=cmd)
        cmd.finish('pressure=%g' % (ret))
