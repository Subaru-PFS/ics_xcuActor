#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class MotorsCmd(object):
    
    # MOTOR PARAMETERS FOR INITIALIZATION used by initCcd    
    velocity = 7400   # microSteps per second
    runCurrent = 70   # percentage of controller peak current 
    holdCurrent = 0   
    microstepping = 16   # Fixed
    homeDistance = 6000 * microstepping # max steps for homing

    stepsPerRev = 200
    microstepsPerRev = microstepping * stepsPerRev
    stepsOffHome = 2
    zeroOffset = 100 * microstepping
    
    # CONVERSION FACTORS TO CONVERT MICRONS TO MOTOR STEPS
    # microsteps per rev * pivot ratio / screw pitch
    a_microns_to_steps = stepsPerRev * 36.77 / 317.5
    b_microns_to_steps = stepsPerRev * 36.02 / 317.5
    c_microns_to_steps = stepsPerRev * 36.02 / 317.5 
    a_microns_to_microsteps = a_microns_to_steps * microstepping
    b_microns_to_microsteps = b_microns_to_steps * microstepping
    c_microns_to_microsteps = c_microns_to_steps * microstepping

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
            ('motors', 'status', self.motorStatus),
            ('motors', 'initDefaults', self.storePowerOnParameters),
            ('motors', 'initCcd', self.initCcd),
            ('motors', 'homeCcd [<axes>]', self.homeCcd),
            ('motors', 'moveCcd [<a>] [<b>] [<c>] [<piston>] [@(microns)] [@(abs)]', self.moveCcd),
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

        self.status = ["Unknown", "Unknown", "Unknown"]
        self.motorStatus(self.actor.bcast)
        
    def motorID(self, motorName):
        """ Translate from all plausible motor/axis IDs to the controller IDs. """

        motorNames = {'a':1, '1':1, 1:1,
                      'b':2, '2':2, 2:2,
                      'c':3, '3':3, 3:3}

        return motorNames[motorName]

    def motorsRaw(self, cmd):
        """ Send a raw AllMotion command to the motor controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmd_txt, cmd=cmd)
        if errCode != "OK":
            cmd.fail('text="code=%s, returned %s"' % (errCode, rest))
        else:
            cmd.finish('text="returned %s"' % (rest))

    def motorStatus(self, cmd, doFinish=True):
        """ query all CCD motor axes """

        getLimitCmd = "?aa%d" # F1 reverses the home direction
        getCountsCmd = "?0"
        for m in 1,2,3:
            # added this to select axis
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('aM%dR' % (m), cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="selection of axis %d failed with code=%s"' % (m, errCode))
    
            errCode, busy, rawLim = self.actor.controllers['PCM'].motorsCmd((getLimitCmd % (m)), cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="query of axis %d limits failed with code=%s"' % (m, errCode))
                return
                # rawLimit data  is ADC values from 0 to 16384... binary based on threshold
            
            farSwitch = 0
            homeSwitch = 0            
            rl = rawLim.split(',')    
            if int(rl[0]) > 8000:
                farSwitch = 1    

            if int(rl[1]) > 8000:
                homeSwitch = 1
                
            if getCountsCmd:
                errCode, busy, rawCnt = self.actor.controllers['PCM'].motorsCmd(getCountsCmd, cmd=cmd)
                if errCode != "OK":
                    cmd.fail('text="query of axis %d counts failed with code=%s"' % (m, errCode))
                    return
            rawCnt = int(rawCnt)
            zeroedCnt = rawCnt - self.zeroOffset
            
            stepCnt = rawCnt // self.microstepping
            if stepCnt * self.microstepping != rawCnt:
                cmd.warn('text="motor %s is not at a full step: %d microsteps"' % (m, rawCnt))
                
            # convert steps to microns
            if m == 1:           
                microns = float(zeroedCnt) / float(self.a_microns_to_microsteps)
            elif m == 2:
                microns = float(zeroedCnt) / float(self.b_microns_to_microsteps)
            else:
                microns = float(zeroedCnt) / float(self.c_microns_to_microsteps)

            status = "OK" if stepCnt >= 100 and not farSwitch else "Unknown"
            self.motorStatus[m-1] = status
            cmd.inform('ccdMotor%d=%s,%s,%s,%s,%0.2f' % (status, m, homeSwitch, farSwitch, stepCnt, microns))

        if doFinish:
            cmd.finish()    

    def _getInitString(self, axis):
        """ Get the per-axis motor controller initialization string. """
        
        # aM%d   - select motor %d
        # n2     - enable limit switches
        # f0     - limit switches are normally closed
        # F0     - positive steps move away from home
        # V%d    - set velocity
        # h%d    - set hold current
        # m%d    - set drive current
        #
        initCmd = "aM%dn2f0F0V%dh%dm%dR"

        return initCmd % (axis, self.velocity, self.holdCurrent, self.runCurrent)
    
    def initCcd(self, cmd):
        """ Initialize all CCD motor axes: set scales and limits, etc. """

        initCmd2 = ""
        for m in 1,2,3:
            initCmd = self._getInitString(m)
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd,
                                                                          cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
            if initCmd2:
                errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd2 % (m), cmd=cmd)
                if errCode != "OK":
                    cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                    return
        cmd.finish()

    def storePowerOnParameters(self, cmd):
        s0instruction = "s0e1M500e2M500e3R" # contoller executes stored programs 1,2 & 3
        motorParams = "s%d%s"
        
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(s0instruction, cmd=cmd) 
        if errCode != "OK":
            cmd.fail('text="init of s0 instruction failed with code=%s"' % (errCode))
            return
            
        for m in 1,2,3:
            initCmd = self._getInitString(m)
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(motorParams % (m, initCmd),
                                                                          cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
        
        cmd.finish()

    def homeCcd(self, cmd):
        """ Home CCD motor axes.

        Individual axes can be specified with axes=A,B

        The timeouts are currently too short.
        """

        homeCmd = "aM%dZ%d" + "gS03P1G200z%dR" % (self.zeroOffset)
        
        cmdKeys = cmd.cmd.keywords
        _axes = cmdKeys['axes'].values if 'axes' in cmdKeys else [1,2,3]

        try:
            axes = [self.motorID(a) for a in _axes]
        except KeyError as e:
            cmd.fail('txt="unknown axis name in %r: %s"' % (_axes, e))
            return

        cmd.inform('text="homing axes: %s"' % (axes))
        for m in axes:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(homeCmd % (m, self.homeDistance), 
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=self.homeDistance/self.velocity + 3,
                                                                          cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="home of axis %d failed with code=%s"' % (m, errCode))
                return

        self.motorStatus(cmd)

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
        piston = cmdKeys['piston'].values[0] if 'piston' in cmdKeys else None
        
        a = cmdKeys['a'].values[0] if 'a' in cmdKeys else None
        b = cmdKeys['b'].values[0] if 'b' in cmdKeys else None
        c = cmdKeys['c'].values[0] if 'c' in cmdKeys else None

        if (piston is None and
                a is None and
                b is None and
                c is None): 
            cmd.fail('text="No motion specified"')
            return

        if (piston is None) and (a is not None or
                                 b is not None or
                                 c is not None):
            cmd.fail('text="Either piston or home or one or more of a,b,c must be specified."')
            return

        if piston is not None:
            a = b = c = piston
        if moveMicrons:
            if a is not None:
                a = int(float(a) * self.a_microns_to_steps) * self.microstepping
            if b is not None:
                b = int(float(b) * self.b_microns_to_steps) * self.microstepping
            if c is not None:
                c = int(float(c) * self.c_microns_to_steps) * self.microstepping
        else:
            if a is not None:
                a *= self.microstepping
            if b is not None:
                b *= self.microstepping
            if c is not None:
                c *= self.microstepping

        if absMove:
            if a is not None:
                a += self.zeroOffset
            if b is not None:
                b += self.zeroOffset
            if c is not None:
                c += self.zeroOffset
            
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
                                                                      maxTime=5.0,
                                                                      cmd=cmd)

        if errCode != "OK":
            self.motorStatus(cmd, doFinish=False)
            cmd.fail('text="move failed with code=%s"' % (errCode))
        else:
            self.motorStatus(cmd)

    def haltMotors(self, cmd):
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('T', cmd=cmd)
        cmd.finish()
        
        
