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
            ('gauge', '<setRaw>', self.setRaw),
            ('gauge', '<getRaw>', self.getRaw),
            
            ('gauge', 'status', self.pcmPressure),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_gauge", (1, 1),
                                        keys.Key("getRaw", types.Int(),
                                                 help='the MPT200 query'),
                                        keys.Key("setRaw",
                                                 types.CompoundValueType(types.Int(help='the MPT200 code'),
                                                                         types.String(help='the MPT200 value'))),
                                        )
        
    def pcmPressure(self, cmd, doFinish=True):
        """ Fetch the latest pressure reading from the cryostat ion gauge. """

        ret = self.actor.controllers['PCM'].pressure(cmd=cmd)

        if doFinish:
            cmd.finish('pressure=%g' % (ret))
        else:
            cmd.inform('pressure=%g' % (ret))

        return ret
    
    def getRaw(self, cmd):
        """ Send a direct query command to the PCM's gauge controller. """

        cmdCode = cmd.cmd.keywords['getRaw'].values[0]
        ret = self.actor.controllers['PCM'].gaugeRawQuery(cmdCode, cmd=cmd)
        cmd.finish('text=%s' % (qstr("returned %r" % ret)))

    def setRaw(self, cmd):
        """ Send a direct control command to the PCM's gauge controller. """

        parts = cmd.cmd.keywords['setRaw'].values[0]
        cmdCode, cmdValue = parts

        cmd.diag('text="code=%r, value=%r"' % (cmdCode, cmdValue))
    
        ret = self.actor.controllers['PCM'].gaugeRawSet(cmdCode, cmdValue, cmd=cmd)
        cmd.finish('text=%s' % (qstr("returned %r" % ret)))

    def pcmGaugeRaw(self, cmd):
        """ Send a raw text command to the PCM's gauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]
        
        ret = self.actor.controllers['PCM'].gaugeRawCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

