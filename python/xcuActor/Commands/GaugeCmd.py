#!/usr/bin/env python

from builtins import object
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
        self.keys = keys.KeysDictionary("xcu_gauge", (1, 1),
                                        )

    def pcmPressure(self, cmd, doFinish=True):
        """ Fetch the latest pressure reading from the cryostat ion gauge. """

        ret = self.actor.controllers['PCM'].gaugeRawCmd('rVac,torr', cmd=cmd)
        ret = float(ret)

        if doFinish:
            cmd.finish('pressure=%g' % (ret))
        else:
            cmd.inform('pressure=%g' % (ret))

        return ret

    def pcmGaugeRaw(self, cmd):
        """ Send a raw text command to the PCM's gauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['PCM'].gaugeRawCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))
