#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
from opscore.utility.qstr import qstr

class LtempsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ltemps', '@raw', self.tempsRaw),
            ('ltemps', 'status', self.status),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_ltemps", (1, 1),

                                        )

    def tempsRaw(self, cmd):
        """ Send a raw command to the temps controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['ltemps'].tempsCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def status(self, cmd):
        self.actor.controllers['ltemps'].status(cmd=cmd)
        cmd.finish()
