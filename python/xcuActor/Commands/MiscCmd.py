#!/usr/bin/env python

import opscore.protocols.keys as keys

class MiscCmd(object):

    def __init__(self, actor):
        self.actor = actor

        self.vocab = [
            ('setCryoMode', '@(offline|roughing|pumpdown|cooldown|operation|warmup|bakeout)', self.setCryoMode),
            ('setRoughActor', '@(rough1|rough2)', self.setRoughActor),
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

    def setRoughActor(self, cmd):
        """ Set the current roughing actor. """

        cmdKeys = cmd.cmd.keywords
        for n in 'rough1', 'rough2':
            if n in cmdKeys:
                self.actor.roughName = n

        cmd.finish(f'text="roughName={self.actor.roughName}')
