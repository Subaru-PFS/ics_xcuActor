#!/usr/bin/env python

from builtins import range
from builtins import object

import opscore.protocols.keys as keys
import opscore.protocols.types as types

class IonpumpCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ionpump', '@raw', self.ionpumpRaw),
            ('ionpumpRead', '@raw', self.ionpumpReadRaw),
            ('ionpumpWrite', '@raw', self.ionpumpWriteRaw),
            ('ionpump', 'ident', self.ident),
            ('ionpump', 'status [@pump1] [@pump2]', self.status),
            ('ionpump', 'off [@pump1] [@pump2]', self.off),
            ('ionpump', 'on [@pump1] [@pump2] [<spam>]', self.on),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_ionpump", (1, 1),
                                        keys.Key("spam", types.Int(),
                                                 help='how many times to poll for status'),

                                        )

    def ionpumpRaw(self, cmd):
        """ Send a raw command to the ionpump controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['ionpump'].ionpumpCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ionpumpReadRaw(self, cmd):
        """ Send a raw read command to the ionpump controller. 

        The format is simply the register number: `raw=REGNUM`.
        """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['ionpump'].sendReadCommand(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ionpumpWriteRaw(self, cmd):
        """Send a raw write command to the ionpump controller. 

        The format is `raw=REGNUM VALUE`.

        Note that the command does not know about types, so the value
        has to be padded if necessary. Ints are 6 digits, strings
        (floats) are 10. E.g. to set the controller for which we want
        to read status, send `raw=505 000003`.

        """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        win, value = cmd_txt.split()

        ret = self.actor.controllers['ionpump'].sendWriteCommand(win, value, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def ident(self, cmd):
        """ Return the ionpump ids. 

         - the ionpump model
         - DSP software version
         - PIC software version
         - full speed in RPM

        """
        ret = self.actor.controllers['ionpump'].ident(cmd=cmd)
        cmd.finish('ident=%s' % (','.join(ret)))

    def status(self, cmd):
        cmdArgs = cmd.cmd.keywords
        pumps = []
        if 'pump1' in cmdArgs:
            pumps.append(0)
        if 'pump2' in cmdArgs:
            pumps.append(1)
        if not pumps:
            pumps.extend([0,1])

        for p_i in pumps:
            self.actor.controllers['ionpump'].readOnePump(p_i, cmd=cmd)
        cmd.finish()

    def on(self, cmd=None):
        cmdArgs = cmd.cmd.keywords
        pump1 = 'pump1' in cmdArgs
        pump2 = 'pump2' in cmdArgs
        if not pump1 and not pump2:
            pump1 = pump2 = True

        npumps = self.actor.controllers['ionpump'].npumps
        ret = self.actor.controllers['ionpump'].on(pump1=pump1, pump2=pump2, cmd=cmd)
        if '5' in ret:
            cmd.fail('text="ion pump controller is in LOCAL mode!"')
            return

        spam = cmdArgs['spam'].values[0] if 'spam' in cmdArgs else 0
        for ii in range(spam):
            for i in range(npumps):
                self.actor.controllers['ionpump'].readOnePump(i, cmd=cmd)
        cmd.finish()

    def off(self, cmd=None):
        cmdArgs = cmd.cmd.keywords
        pump1 = 'pump1' in cmdArgs
        pump2 = 'pump2' in cmdArgs
        if not pump1 and not pump2:
            pump1 = pump2 = True

        ret = self.actor.controllers['ionpump'].off(pump1=pump1, pump2=pump2, cmd=cmd)
        if '5' in ret:
            cmd.fail('text="ion pump controller is in LOCAL mode!"')
        else:
            cmd.finish()
