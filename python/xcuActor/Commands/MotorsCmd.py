#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class MotorsCmd(object):
    
    # MOTOR PARAMETERS FOR INITIALIZATION used by initCcd    
    velocity=7400   # microSteps per second
    runCurrent=54   # percentage of controller peak current 
    holdCurrent=0   
    homeDistance=100000 # max steps for homing
    
    #CONVERSION FACTORS TO CONVERT MICRONS TO MOTOR STEPS
    # microsteps per rev * pivot ratio / screw pitch
    a_microns_to_steps = 3600.0 * 36.02 / 317.5
    b_microns_to_steps = 3600.0 * 36.02 / 317.5
    c_microns_to_steps = 3600.0 * 36.77 / 317.5 

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('motors', '@raw', self.motorsRaw),
            ('motors', 'initCcd', self.initCcd),
            ('motors', 'homeCcd [<axes>]', self.homeCcd),
            ('motors', 'moveCcd [<a>] [<b>] [<c>] [<piston>] [@(abs)] [@(rel)]', self.moveCcd),
            ('motors', 'halt', self.haltMotors),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_motors", (1, 1),
                                        keys.Key("axes", types.String()*(1,3),
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

    def motorID(self, motorName):
        """ Translate from all plausible motor/axis IDs to the controller IDs. """

        motorNames = {'a':1, '1':1, 1:1,
                      'b':2, '2':2, 2:2,
                      'c':3, '3':3, 3:3}

        return motorNames[motorName]

    def motorsRaw(self, cmd):
        """ Send a raw AllMotion command to the motor controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmd_txt)
        if errCode != "OK":
            cmd.fail('text="code=%s, returned %s"' % (errCode, rest))
        else:
            cmd.finish('text="returned %s"' % (rest))

    def initCcd(self, cmd):
        """ Initialize all CCD motor axes: set scales and limits, etc. """

        scaleCmd = "~10%d01"
        initCmd = "aM%dn2f0V%dh%dm%dR" # F1 reverses the home direction
        initCmd2 = ""
        for m in 1,2,3:
            ret = self.actor.controllers['PCM'].pcmCmd(scaleCmd % (m), cmd=cmd)
            if ret != "Success":
                cmd.fail('text="setting scale for axis %d failed with: %s"' % (m, ret))
                return
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd % (m, self.velocity, self.holdCurrent, self.runCurrent), cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
            if initCmd2:
                errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd2 % (m), cmd=cmd)
                if errCode != "OK":
                    cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                    return
        cmd.finish()

    def homeCcd(self, cmd):
        """ Home CCD motor axes.

        Individual axes can be specified with axes=A,B

        The timeouts are currently too short.
        """

        homeCmd = "aM%dZ%dR"
        
        cmdKeys = cmd.cmd.keywords
        _axes = cmdKeys['axes'].values if 'axes' in cmdKeys else [1,2,3]

        try:
            axes = [self.motorID(a) for a in _axes]
        except KeyError as e:
            cmd.fail('txt="unknown axis name in %r: %s"' % (_axes, e))
            return

        cmd.inform('text="homing axes: %r"' % (axes))
        for m in axes:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(homeCmd % (m, self.homeDistance), 
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=5.0,
                                                                          cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="home of axis %d failed with code=%s"' % (m, errCode))
                return

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
        moveMicrons = 'microns' in cmdKeys
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
            piston = -99999
        if piston:
            a = b = c = piston

        if a is not None:
            a *= 16
        if b is not None:
            b *= 16
        if c is not None:
            c *= 16

        if absMove:
            cmdStr = "A%s,%s,%s,R" % (a if a is not None else '',
                                      b if b is not None else '',
                                      c if c is not None else '')
        else:
            cmdStr = "P%s,%s,%s,R" % (a if a is not None else '',
                                      b if b is not None else '',
                                      c if c is not None else '')

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmdStr,
                                                                      waitForIdle=True,
                                                                      returnAfterIdle=True,
                                                                      maxTime=5.0)

        if errCode != "OK":
            cmd.fail('text="move failed with code=%s"' % (errCode))
        else:
            cmd.finish()

    def haltMotors(self, cmd):
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('T')
        cmd.finish()
        
        
