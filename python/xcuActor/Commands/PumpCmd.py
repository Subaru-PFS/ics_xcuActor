#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class PumpCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('pumpraw', '@raw', self.pumpRaw),
            ('pump', 'ident', self.ident),
            ('pump', 'status', self.status),
            ('pump', 'start', self.startPump),
            ('pump', 'stop', self.stopPump),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_pump", (1, 1),

                                        )

    def pumpRaw(self, cmd):
        """ Send a raw command to the pump controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['pump'].pumpCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ident(self, cmd):
        ret = self.actor.controllers['pump'].ident(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def status(self, cmd):
        self.actor.controllers['pump'].status(cmd=cmd)
        cmd.finish()

    def startPump(self, cmd):
        ret = self.actor.controllers['pump'].startPump(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def stopPump(self, cmd):
        ret = self.actor.controllers['pump'].stopPump(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))
