#!/usr/bin/env python

import opscore.protocols.keys as keys

class MiscCmd(object):

    def __init__(self, actor):
        self.actor = actor

        self.vocab = [
            ('setCryoMode', '@(offline|standby|pumpdown|cooldown|operation|warmup|bakeout)', self.setCryoMode),
        ]

        self.keys = keys.KeysDictionary("xcu_misc", (1, 1),
                                        )
    def setCryoMode(self, cmd):
        """ Set the current cryomode. """

        cmdKeys = cmd.cmd.keywords

        newMode = None
        for mode in self.actor.cryoMode.validModes:
            if mode in cmdKeys:
                newMode = mode
                break

        if newMode is None:
            cmd.fail('text="no valid mode requested!"')
            return

        self.actor.cryoMode.setMode(newMode, cmd=cmd)
        cmd.finish()

