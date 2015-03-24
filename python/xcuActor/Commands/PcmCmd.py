#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class PcmCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('pcm', '@raw', self.pcmRaw),
            ('init', '', self.init),
            ('home', '', self.home),
            ('moveRel', '', self.moveRel),
            ('moveAbs', '', self.moveAbs),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_pcm", (1, 1),
                                        )

    def pcmRaw(self, cmd):
        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmd_txt)
        if errCode != "OK":
            cmd.fail('text="code=%s, returned %s"' % (errCode, rest))
        else:
            cmd.finish('text="returned %s"' % (rest))

    def init(self, cmd):
        initCmd = "aM%dn2f0V3200,h0m30R"
        for m in 1,2,3:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd % (m))
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
        cmd.finish()

    def home(self, cmd):
        raise UnimplementedError("home")

    def moveRel(self, cmd):
        raise UnimplementedError("moveRel")

    def moveAbs(self, cmd):
        raise UnimplementedError("moveAbs")

