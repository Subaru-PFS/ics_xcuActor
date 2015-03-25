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

            ('motors', '@raw', self.motorsRaw),
            ('init', '', self.init),
            ('home', '[<axes>]', self.home),
            ('moveCcd', '[<a>] [<b>] [<c>] [<piston>] [@(abs)] [@(rel)]', self.moveCcd),

            ('power', '@(on|off) @(motors|bee|fee|gauge)', self.power),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_pcm", (1, 1),
                                        keys.Key("axes", types.Int()*(1,3),
                                                 help='list of motor names'),
                                        keys.Key("a", types.Int(),
                                                 help='the number of ticks to move actuator A'),
                                        keys.Key("b", types.Int(),
                                                 help='the number of ticks to move actuator B'),
                                        keys.Key("c", types.Int(),
                                                 help='the number of ticks to move actuator C'),
                                        keys.Key("piston", types.Int(),
                                                 help='the number of ticks to move actuators A,B, and C'),


                                        )

    def pcmRaw(self, cmd):
        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['PCM'].pcmCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def motorsRaw(self, cmd):
        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmd_txt)
        if errCode != "OK":
            cmd.fail('text="code=%s, returned %s"' % (errCode, rest))
        else:
            cmd.finish('text="returned %s"' % (rest))

    def init(self, cmd):
        scaleCmd = "~20%d016"
        initCmd = "aM%dn2f0V3200h0m30R"
        for m in 1,2,3:
            ret = self.actor.controllers['PCM'].pcmCmd(scaleCmd % (m))
            if ret != "Success":
                cmd.fail('text="setting scale for axis %d failed with: %s"' % (m, ret))
                return

            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd % (m))
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
        cmd.finish()

    def power(self, cmd):
        """ power some PCM components on or off.

        Arguments:
           on/off                - one of the two.
           motors/gauge/bee/fee  - one subsystem to power on/off.
        """
        
        cmdKeys = cmd.cmd.keywords
        if 'on' in cmdKeys:
            turnOn = True
        elif 'off' in cmdKeys:
            turnOn = False
        else:
            cmd.fail('text="neither on nor off was specified!"')
            return

        systems = self.actor.controllers['PCM'].powerPorts
        for i in range(len(systems)):
            if systems[i] in cmdKeys:
                ret = self.actor.controllers['PCM'].powerCmd(systems[i], turnOn=turnOn, cmd=cmd)
                if ret != 'Success':
                    cmd.fail('text="failed to turn %s %s: %s"' % (systems[i],
                                                                  'on' if turnOn else 'off',
                                                                  ret))
                    return
        cmd.finish()

    def home(self, cmd):
        homeDistance = 10000  # 1000000
        homeCmd = "aM%dZ%dR"
        
        cmdKeys = cmd.cmd.keywords
        axes = cmdKeys['axes'].values if 'axes' in cmdKeys else [1,2,3]

        cmd.inform('text="homing axes: %r"' % (axes))
        for m in axes:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(homeCmd % (m, homeDistance))
            if errCode != "OK":
                cmd.fail('text="home of axis %d failed with code=%s"' % (m, errCode))
                return
            time.sleep(4)
        cmd.finish()

    def moveCcd(self, cmd):
        """ Adjust the position of the detector motors. 
        Arguments:
            a=ticks b=ticks c=ticks    - one or more motor commands, in ticks.
              or
            piston=ticks
            abs           - if set, go to absolute position.
        """

        cmdKeys = cmd.cmd.keywords

        absMove = 'abs' in cmdKeys 
        goHome = 'home' in cmdKeys 
        piston = cmdKeys['piston'].values[0] if 'piston' in cmdKeys else None
        
        a = cmdKeys['a'].values[0] if 'a' in cmdKeys else None
        b = cmdKeys['b'].values[0] if 'b' in cmdKeys else None
        c = cmdKeys['c'].values[0] if 'c' in cmdKeys else None

        if not (piston or a or b or c or goHome): 
            cmd.fail('text="No motion specified"')
            return

        if piston and (a or b or c) and goHome:
            cmd.fail('text="Either piston or home or one or more of a,b,c must be specified."')
            return

        if goHome:
            piston = -50000
        if piston:
            a = b = c = piston

        if absMove:
            cmdStr = "A%s,%s,%s,R" % (a if a is not None else '',
                                      b if b is not None else '',
                                      c if c is not None else '')
        else:
            cmdStr = "P%s,%s,%s,R" % (a if a is not None else '',
                                      b if b is not None else '',
                                      c if c is not None else '')

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmdStr)
        if errCode != "OK":
            cmd.fail('text="move failed with code=%s"' % (errCode))
        else:
            cmd.finish()

    def stop(self, cmd):
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('T')
        
    def moveRel(self, cmd):
        raise UnimplementedError("moveRel")

    def moveAbs(self, cmd):
        raise UnimplementedError("moveAbs")

