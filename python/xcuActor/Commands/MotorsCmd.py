#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class MotorsCmd(object):
    
    # MOTOR PARAMETERS FOR INITIALIZATION used by initCcd    
    velocity = 7400             # microSteps per second
    runCurrent = 70             # percentage of controller peak current 
    holdCurrent = 0   
    microstepping = 16          # Fixed with our controller.

    stepsPerRev = 200
    microstepsPerRev = microstepping * stepsPerRev
    stepsOffHome = 2
    zeroOffset = 100 * microstepping
    
    # CONVERSION FACTORS TO CONVERT MICRONS TO MOTOR STEPS
    # microsteps per rev * pivot ratio / screw pitch
    a_microns_to_steps = stepsPerRev * 36.77 / 635.0
    b_microns_to_steps = stepsPerRev * 36.02 / 635.0
    c_microns_to_steps = stepsPerRev * 36.02 / 635.0 
    a_microns_to_microsteps = a_microns_to_steps * microstepping
    b_microns_to_microsteps = b_microns_to_steps * microstepping
    c_microns_to_microsteps = c_microns_to_steps * microstepping

    homeDistance = 400 * a_microns_to_microsteps # max steps for homing
    
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
            ('motors', 'init', self.initCcd),
            ('motors', 'homeCcd [<axes>]', self.homeCcd),
            ('motors', 'home [<axes>]', self.homeCcd),
            ('motors', 'moveCcd [<a>] [<b>] [<c>] [<piston>] [@(microns)] [@(abs)] [@(force)]', self.moveCcd),
            ('motors', 'move [<a>] [<b>] [<c>] [<piston>] [@(microns)] [@(abs)] [@(force)]', self.moveCcd),
            ('motors', 'halt', self.haltMotors),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_motors", (1, 1),
                                        keys.Key("axes", types.String()*(1,3),
                                                 help='list of motor names'),
                                        keys.Key("a", types.Float(),
                                                 help='the number of ticks/microns to move actuator A'),
                                        keys.Key("b", types.Float(),
                                                 help='the number of ticks/microns to move actuator B'),
                                        keys.Key("c", types.Float(),
                                                 help='the number of ticks/microns to move actuator C'),
                                        keys.Key("piston", types.Float(),
                                                 help='the number of ticks/microns to move actuators A,B, and C'),
                                        )

        self._clearStatus()

        try:
            self.brokenLAMr1A = self.actor.config.getboolean('hacks', 'brokenLAMr1A')
        except:
            self.brokenLAMr1A = False

    def _clearStatus(self):
        self.status = ["Unknown", "Unknown", "Unknown"]
        self.positions = [0, 0, 0]
        
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

    def _getSwitches(self, axis, cmd):
        """ Fetch the switch positions for the given axis

        Args
        ----
        axis - {a,b,c,1,2,3}


        Returns
        -------
        low, high - int
          The states of the given switches. 0=clear, 1=set

        """
        getLimitCmd = "?aa%d"

        m = self.motorID(axis)
        
        errCode, busy, rawLim = self.actor.controllers['PCM'].motorsCmd((getLimitCmd % (m)),
                                                                        maxTime=2.0,
                                                                        cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("query of axis %d limits failed with code=%s and result=%s" %
                               (m, errCode, rawLim))
            
        farSwitch = 0
        homeSwitch = 0            
        rl = rawLim.split(',')    
        if int(rl[0]) > 8000:
            farSwitch = 1    

        if int(rl[1]) > 8000:
            homeSwitch = 1
                
        return homeSwitch, farSwitch
        
    def _getPositions(self, cmd):
        """ Fetch all axis positions

        Returns
        -------
        
        The states of the three axis positions.

        """
        
        getPosCmd = "?aA"

        errCode, busy, rawPos = self.actor.controllers['PCM'].motorsCmd((getPosCmd), cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("query of axis positions failed with code=%s" % (errCode))
            
        allPos = [int(p) for p in rawPos.split(',')]
        return allPos[:3]
    
    def motorStatus(self, cmd, doFinish=True):
        """ query all CCD motor axes """

        self.actor.controllers['PCM'].waitForIdle(maxTime=1.0, cmd=cmd)
        
        positions = self._getPositions(cmd)
        for m_i in range(3):
            m = m_i + 1
            
            homeSwitch, farSwitch = self._getSwitches(m, cmd)
            rawCnt = positions[m_i]
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

            # Declare axis good unless at/beyond any limit or previous suspect.
            if (self.brokenLAMr1A and m == 1):
                status = 'OK' if self.status[m-1] != 'Unknown' else 'Unknown'
            elif (self.status[m-1] != 'Unknown' and
                  stepCnt >= 100 and
                  not farSwitch and
                  not homeSwitch):
                status = "OK"
            else:
                status = "Unknown"
                
            self.status[m-1] = status
            self.positions[m-1] = stepCnt
            if status != 'OK':
                report = cmd.warn
            else:
                report = cmd.inform
            report('ccdMotor%d=%s,%s,%s,%s,%0.2f' % (m, status,
                                                     homeSwitch, farSwitch,
                                                     stepCnt, microns))
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

        self._clearStatus()
        
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
        """ Initialize the boot all CCD motor axes: set scales and limits, etc. """

        s0instruction = "s0e1M500e2M500e3R" # contoller executes stored programs 1,2 & 3
        motorParams = "s%d%s"
        
        cmd.inform('text="burning in init commands register 0"')
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(s0instruction,
                                                                      waitForIdle=True, returnAfterIdle=True,
                                                                      maxTime=3.0, waitTime=1.0,
                                                                      cmd=cmd) 
        if errCode != "OK":
            cmd.fail('text="init of s0 instruction failed with code=%s"' % (errCode))
            return
            
        for m in 1,2,3:
            initCmd = self._getInitString(m)
            cmd.inform('text="burning in init commands for axis %d"' % (m))
            try:
                errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(motorParams % (m, initCmd),
                                                                              waitForIdle=True, returnAfterIdle=True,
                                                                              maxTime=3.0, waitTime=1.0,
                                                                              cmd=cmd)
            except RuntimeError as e:
                if not e.message.startswith('no response'):
                    raise
                else:
                    cmd.warn('text="blowing through expected glitch: %s"' % (e))
                    
            if errCode != "OK":
                cmd.fail('text="init of axis %d failed with code=%s"' % (m, errCode))
                return
        
        cmd.finish()

    def _calcMoveTime(self, distance):
        return distance/self.velocity
        
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

        maxTime = self._calcMoveTime(self.homeDistance) + 5.0
        for m in axes:
            self.status[m-1] = "Homing"
            self.positions[m-1] = 0
            
            cmd.inform('text="homing axis %s: maxTime=%0.2f"' % (m, maxTime))
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(homeCmd % (m, self.homeDistance), 
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=maxTime,
                                                                          cmd=cmd)
            if errCode != "OK":
                cmd.fail('text="home of axis %d failed with code=%s"' % (m, errCode))
                return
        cmd.inform('text="axes homed: %s"' % (axes))

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
        force = 'force' in cmdKeys
        
        a = cmdKeys['a'].values[0] if 'a' in cmdKeys else None
        b = cmdKeys['b'].values[0] if 'b' in cmdKeys else None
        c = cmdKeys['c'].values[0] if 'c' in cmdKeys else None

        if (piston is None and
                a is None and
                b is None and
                c is None): 
            cmd.fail('text="No motion specified"')
            return

        someAxis = a is not None and b is not None and c is not None
        if (piston is not None) and someAxis:
            cmd.fail('text="Either piston or one or more of a,b,c must be specified."')
            return

        if piston is not None:
            a = b = c = piston

        if not moveMicrons:
            # Only allow integer steps
            if ((a is not None and int(a) != a) or
                (b is not None and int(b) != b) or
                (c is not None and int(c) != c)):
                
                cmd.fail('text="steps must be integral"')
                return

        self.motorStatus(cmd, doFinish=False)

        if force:
            cmd.warn('text="YOU ARE FORCING A MOVE!!!"')
        else:
            if self.brokenLAMr1A:
                axesToTest = [b,c] 
            else:
                axesToTest = [a,b,c] 
            for i, ax in enumerate(axesToTest):
                if ax is not None and self.status[i] != 'OK':
                    cmd.fail('text="axis %s (at least) needs to be homed"' % chr((i + ord('a'))))
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

        maxDistance = 0
        if absMove:
            if a is not None:
                a += self.zeroOffset
                maxDistance = max(maxDistance, abs(a - self.positions[0]))
            if b is not None:
                b += self.zeroOffset
                maxDistance = max(maxDistance, abs(b - self.positions[1]))
            if c is not None:
                c += self.zeroOffset
                maxDistance = max(maxDistance, abs(c - self.positions[2]))
            
            cmdStr = "A%s,%s,%s,R" % (int(a) if a is not None else '',
                                      int(b) if b is not None else '',
                                      int(c) if c is not None else '')
        else:
            if a is not None:
                maxDistance = abs(a)
            if b is not None:
                maxDistance = max(maxDistance, abs(b))
            if c is not None:
                maxDistance = max(maxDistance, abs(c))
                
            cmdStr = "P%s,%s,%s,R" % (int(a) if a is not None else '',
                                      int(b) if b is not None else '',
                                      int(c) if c is not None else '')

        try:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmdStr,
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=self._calcMoveTime(maxDistance) + 3.0,
                                                                          cmd=cmd)
        except Exception as e:
            errCode = "uncaught error: %s" % (e)
            
        if errCode != "OK":
            self.motorStatus(cmd, doFinish=False)
            cmd.fail('text="move failed with code=%s"' % (errCode))
        else:
            self.motorStatus(cmd)

    def haltMotors(self, cmd):
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('T', cmd=cmd)
        cmd.finish()
        
        
