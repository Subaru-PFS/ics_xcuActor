#!/usr/bin/env python

from builtins import object
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class GatevalveCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('gatevalve', 'status', self.status),
            ('gatevalve', 'open', self.open),
            ('gatevalve', 'close', self.close),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gatevalve", (1, 1),
        )

    def status(self, cmd):
        """ Generate all gatevalve keys."""

        self.actor.controllers['gatevalve'].status(cmd=cmd)
        cmd.finish()

    def open(self, cmd):
        """ Enable gatevalve to be opened. """

        self.actor.controllers['gatevalve'].open(cmd=cmd)
        cmd.finish()
        
    def close(self, cmd):
        """ Disable gatevalve to be opened. """

        self.actor.controllers['gatevalve'].close(cmd=cmd)
        cmd.finish()
        
