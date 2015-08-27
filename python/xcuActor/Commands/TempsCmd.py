#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
from opscore.utility.qstr import qstr

class TempsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('temps', '@raw', self.tempsRaw),
            ('temps', 'status', self.status),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_temps", (1, 1),
                                        )

    def tempsRaw(self, cmd):
        """ Send a raw command to the temps controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['temps'].tempsCmd(cmd_txt, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    def status(self, cmd):
        temps = self.actor.controllers['temps'].fetchTemps(cmd=cmd)
        cmd.finish('temps=%s' % ', '.join(['%0.3f' % (t) for t in temps]))
