#!/usr/bin/env python

import time

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
            ('pcm', 'status', self.udpStatus),

            ('power', '@(on|off) @(motors|gauge|p3|temps|bee|fee|interlock|p8|all) [@(force)]', self.power),

            ('gauge', 'status', self.gaugeStatus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_pcm", (1, 1),
                                        )

    def pcmRaw(self, cmd):
        """ Send a raw command to the PCM controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['PCM'].pcmCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def gaugeRaw(self, cmd):
        """ Send a raw command to the gauge controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['PCM'].gaugeCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %s"' % (qstr(ret)))

    def gaugeStatus(self, cmd):
        ret = self.actor.controllers['PCM'].gaugeStatus(cmd=cmd)
        cmd.finish('pressure=%g' % (ret))

    def udpStatus(self, cmd):
        """ Force generation of the UDP keywords which we most care about. """

        self.actor.controllers['pcmUdp'].status(cmd=cmd)
        cmd.finish()

    def power(self, cmd):
        """ Power some PCM components on or off.

        Arguments:
           on/off                - one of the two.
           motors/gauge/bee/fee  - one subsystem to power on/off.
           force               
        """
        
        cmdKeys = cmd.cmd.keywords
        if 'on' in cmdKeys:
            turnOn = True
        elif 'off' in cmdKeys:
            turnOn = False
        else:
            cmd.fail('text="neither on nor off was specified!"')
            return

        # Assume that we are running on the BEE, and disallow easily powering ourself off.
        if not turnOn and ('bee' in cmdKeys or 'all' in cmdKeys):
            if 'force' not in cmdKeys:
                cmd.fail('text="You must specify force if you want to turn the bee off"')
                return

        systems = self.actor.controllers['PCM'].powerPorts
        for i in range(len(systems)):
            if 'all' in cmdKeys or systems[i] in cmdKeys:
                ret = self.actor.controllers['PCM'].powerCmd(systems[i], turnOn=turnOn, cmd=cmd)
                if ret != 'Success':
                    cmd.fail('text="failed to turn %s %s: %s"' % (systems[i],
                                                                  'on' if turnOn else 'off',
                                                                  ret))
                    return
        cmd.finish()


