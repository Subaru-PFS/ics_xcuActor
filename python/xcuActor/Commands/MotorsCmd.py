#!/usr/bin/env python

import numpy as np
from astropy import time as astroTime

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
from ics.utils import instdata

class MotorsCmd(object):

    # MOTOR PARAMETERS FOR INITIALIZATION used by initCcd
    velocity = 7400             # microSteps per second
    runCurrent = 70             # percentage of controller peak current
    holdCurrent = 0
    microstepping = 16          # Fixed with our controller.

    stepsPerRev = 200
    microstepsPerRev = microstepping * stepsPerRev
    stepsOffHome = 2
    stepsNearLimit = 10          # How close we dare to slew to a limit switch
    zeroOffset = 100 * microstepping
    leadScrewPitch = 700.0      # um/rev

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
            ('motors', 'moveFocus [<microns>] [@(abs)]', self.moveFocus),
            ('motors', 'halt', self.haltMotors),
            ('motors', '@(toSwitch) @(a|b|c) @(home|far) @(set|clear)', self.toSwitch),
            ('motors', '@(toCenter|toFocus|nearFar|nearHome)', self.moveToName),
            ('motors', 'okPositions', self.okPositions),
            ('motors', 'declareMove', self.declareMove),
            ('motors', 'reloadConfig', self.loadConfig),
            ('motors', 'setTilts <spatial> <spectral>', self.setTilts),
            ('motors', 'setArmOffsets [<a>] [<b>] [<c>]', self.setArmOffsets),
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
                                        keys.Key("microns", types.Float(),
                                                 help='the number of microns to move actuators'),
                                        keys.Key("spatial", types.Float(),
                                                 help='microns of spatial tilt'),
                                        keys.Key("spectral", types.Float(),
                                                 help='microns of spectral tilt'),
                                        )

        if self.actor.isNir():
            self.pivotRatios = (40.62, 40.26, 40.26)
            self.armNumToMotorNum = {1:2, 2:3, 3:1}
            self.motorNumToArmNum = {1:3, 2:1, 3:2}
        else:
            self.pivotRatios = (36.77, 36.02, 36.02)
            self.armNumToMotorNum = {1:1, 2:2, 3:3}
            self.motorNumToArmNum = {1:1, 2:2, 3:3}

        # Precalculate conversion factors to convert microns to motor steps
        # microsteps per rev * pivot ratio / screw pitch
        self.a_microns_to_steps = self.stepsPerRev * self.pivotRatios[0] / self.leadScrewPitch
        self.b_microns_to_steps = self.stepsPerRev * self.pivotRatios[1] / self.leadScrewPitch
        self.c_microns_to_steps = self.stepsPerRev * self.pivotRatios[2] / self.leadScrewPitch
        self.microns_to_steps = np.array([self.a_microns_to_steps,
                                          self.b_microns_to_steps,
                                          self.c_microns_to_steps])
        self.a_microns_to_microsteps = self.a_microns_to_steps * self.microstepping
        self.b_microns_to_microsteps = self.b_microns_to_steps * self.microstepping
        self.c_microns_to_microsteps = self.c_microns_to_steps * self.microstepping

        self.homeDistance = 400 * self.a_microns_to_microsteps # max steps for homing

        try:
            self.brokenLAMr1A = self.actor.config.getboolean('hacks', 'brokenLAMr1A')
        except:
            self.brokenLAMr1A = False

        self.instData = instdata.InstData(self.actor)
        self.instConfig = instdata.InstConfig(self.actor.name,
                                              idDict=self.actor.ids.idDict)
        self.loadConfig()

    def loadConfig(self, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast
            doFinish = False

        self.farLimits = 0.0,0.0,0.0
        self.tilts = 0.0,0.0,0.0
        self.focus = 0.0

        self.instConfig.reload()
        cfg = self.instConfig['fpa']

        self.range = np.array(cfg['range'])
        self.focus = cfg['focus']
        self.medFocus = cfg.get('medFocus', None)
        self.tilts = np.array(cfg['tilts'])

        cmd.inform(f'fpaTilt={self.tilts[0]:0.2f},{self.tilts[1]:0.2f},{self.tilts[2]:0.2f}')
        cmd.inform(f'fpaRange={self.range[0]:0.2f},{self.range[1]:0.2f},{self.range[2]:0.2f}')
        cmd.inform(f'fpaBestFocus={self.focus:0.2f},{self.medFocus}')

        try:
            self.initializeStatus(cmd)
        except Exception as e:
            cmd.warn(f'text="failed to fetch motors status: {e}"')
            cmd.finish()

    def setTilts(self, cmd):
        """Manually set temporary tilts."""

        cmdKeys = cmd.cmd.keywords
        spectral = cmdKeys['spectral'].values[0]
        spatial = cmdKeys['spatial'].values[0]

        a = spatial
        b = c = -spatial

        b += spectral
        c -= spectral

        self.tilts = np.array([a,b,c])
        cmd.finish(f'fpaTilt={self.tilts[0]:0.2f},{self.tilts[1]:0.2f},{self.tilts[2]:0.2f}')

    def setArmOffsets(self, cmd):
        """Manually set temporary tilts."""

        cmdKeys = cmd.cmd.keywords
        a = cmdKeys['a'].values[0] if 'a' in cmdKeys else self.tilts[0]
        b = cmdKeys['b'].values[0] if 'b' in cmdKeys else self.tilts[1]
        c = cmdKeys['c'].values[0] if 'c' in cmdKeys else self.tilts[2]

        self.tilts = np.array([a,b,c])
        cmd.finish(f'fpaTilt={self.tilts[0]:0.2f},{self.tilts[1]:0.2f},{self.tilts[2]:0.2f}')

    def initializeStatus(self, cmd=None):
        """Establish the status of the motors, matching against persisted positions.

        - load persisted (date, pos)
        - read actual motor positions from the controller

        - if persisted and actual positions match, declare positions
          ok (i.e. set home flags to OK) and generate motor and date
          keys. This will be the normal case.

        - if actual positions are real (> 0) but do not match the
          persisted positions, scream and invalidate everything.

        - for the case when actual positions are == 0 and so indicate
          a power-cycled controller, add a command to allow human to
          declare that persisted positions are good, and to set the
          controller positions from them.

        """

        if cmd is None:
            cmd = self.actor.bcast

        movedTime = 0.0
        cmd.inform('text="validating motor status"')

        self.status = ["Unknown", "Unknown", "Unknown"]
        self.positions = [-1,-1,-1]
        self.positions = self._getCorrectedPosition(cmd)

        try:
            persistedPositions = self.instData.loadKey('motorPositions')
            movedTime = self.instData.loadKey('motorMovedMjd')
        except KeyError:
            cmd.warn('text="no persisted motor positions found. Will use controller positions if valid"')
            persistedPositions = self.positions
        except Exception as e:
            cmd.warn(f'text="no persisted motor positions saved. Will use controller positions if valid: {e}"')
            persistedPositions = self.positions

        controllerCleared = all([self.positions[i] == 0 for i in range(3)])
        if controllerCleared:
            cmd.warn('text="motor controller has been reset: considering persisted positions...."')
            self.positions = persistedPositions

        noMatch = any([self.positions[i] != persistedPositions[i] for i in range(3)])
        if noMatch:
            cmd.warn('text="persisted motor positions do not match controller positions: discarding all"')
            persistedPositions = None
            movedTime = 0
        else:
            self.status = ['OK', 'OK', 'OK']

        cmd.inform(f'fpaMoved={movedTime:0.6f}')
        self.motorStatus(cmd)

    def armNum(self, armId):
        """ Translate from all plausible arm names to the 1-based arm number. """

        armStrings = {'a':1, '1':1, 1:1,
                      'b':2, '2':2, 2:2,
                      'c':3, '3':3, 3:3}

        return armStrings[armId]

    def motorNum(self, armName):
        """ Translate from all plausible arm names to the 1-based motor number. """

        return self.armNumToMotorNum[self.armNum(armName)]

    def armOrderToMotorOrder(self, armList):
        """ Convert a list of items in arm order to motor order. """

        motorList = [armList[self.motorNumToArmNum[m_i]-1] for m_i in (1,2,3)]
        return motorList

    def motorOrderToArmOrder(self, motorList):
        """ Convert a list of items in motor order to arm order. """

        armList = [motorList[self.armNumToMotorNum[a_i]-1] for a_i in (1,2,3)]
        return armList

    def motorsRaw(self, cmd):
        """ Send a raw AllMotion command to the motor controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmd_txt, cmd=cmd)
        if errCode != "OK":
            cmd.fail('text="code=%s, returned %s"' % (errCode, rest))
        else:
            cmd.finish('text="returned %s"' % (rest))

    def okPositions(self, cmd):
        """ Declare that the current positions are good w.r.t. the home switches.

        If the current motor position indicates that we have been power-cycled, fail.
        """

        a,b,c = self._getRawPosition(cmd)
        if a < self.zeroOffset or b < self.zeroOffset or c < self.zeroOffset:
            cmd.fail('text=f"some motors are in invalid positions: {a},{b},{c}"')
            return

        self.status = ["OK", "OK", "OK"]
        self.motorStatus(cmd)

    def _getSwitches(self, arm, cmd):
        """ Fetch the switch positions for the given arm

        Args
        ----
        arm - {a,b,c,1,2,3}


        Returns
        -------
        low, high - int
          The states of the given switches. 0=clear, 1=set

        """
        getLimitCmd = "?aa%d"

        m = self.motorNum(arm)

        errCode, busy, rawLim = self.actor.controllers['PCM'].motorsCmd((getLimitCmd % (m)),
                                                                        maxTime=2.0,
                                                                        cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("query of arm %s (motor %d) limits failed with code=%s and result=%s" %
                               (arm, m, errCode, rawLim))

        farSwitch = 0
        homeSwitch = 0
        rl = rawLim.split(',')
        if int(rl[0]) > 8000:
            farSwitch = 1

        if int(rl[1]) > 8000:
            homeSwitch = 1

        return homeSwitch, farSwitch

    def _getRawPosition(self, cmd):
        """ Fetch all axis positions

        Returns
        -------

        The states of the three arm positions, in arm order

        """

        getPosCmd = "?aA"

        errCode, busy, rawPos = self.actor.controllers['PCM'].motorsCmd((getPosCmd), cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("query of axis positions failed with code=%s" % (errCode))

        motorPos = [int(p) for p in rawPos.split(',')]
        armPos = self.motorOrderToArmOrder(motorPos)

        cmd.debug(f'text="motors={motorPos} arms={armPos}"')
        return np.array(armPos)

    def _getCorrectedPosition(self, cmd):
        """Return full step positions, w.r.t. the home switches

        Parameters
        ----------
        cmd : `Command`
            The controlling command we can report back to.

        Returns
        -------
        array of int
            Full steps, w.r.t. the home switches.
        """


        rawCnt = self._getRawPosition(cmd)
        steps = (rawCnt - self.zeroOffset) // self.microstepping

        return steps

    def declareNewMotorPositions(self, cmd, invalid=False):
        """Called when motors have been moved or are about to be homed.

        Persist current positions and report change time.

        Args
        ----
        cmd : `Command`
          Where to send keywords.
        invalid : `bool`
          Whether the current positions are trash/unknown.
          Used right before homing.

        For now we just generate the MHS keyword which declares that the
        old motor positions have been invalidated.
        """

        # Use MJD seconds.
        now = float(astroTime.Time.now().mjd)

        keys = dict(motorMovedMjd=now,
                    motorPositions=self._getCorrectedPosition(cmd).tolist())
        self.instData.persistKeys(keys)

        cmd.inform(f'fpaMoved={now:0.6f}')

    def declareMove(self, cmd):
        """Force an announcement that the motors have moved.
        """

        self.declareNewMotorPositions(cmd)
        cmd.finish()

    def _updateMotorStatus(self, cmd):
        """ query all CCD motor axes; update  """

        self.actor.controllers['PCM'].waitForIdle(maxTime=1.0, cmd=cmd)

        positions = self._getRawPosition(cmd)
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
                microns = zeroedCnt/self.a_microns_to_microsteps
            elif m == 2:
                microns = zeroedCnt/self.b_microns_to_microsteps
            else:
                microns = zeroedCnt/self.c_microns_to_microsteps

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
                cmd.arn('ccdMotor%d=%s,%s,%s,%s,%0.2f' % (m, status,
                                                          homeSwitch, farSwitch,
                                                          stepCnt, microns))
    def motorStatus(self, cmd, doFinish=True):
        """ query all CCD motor axes """

        self.actor.controllers['PCM'].waitForIdle(maxTime=1.0, cmd=cmd)

        positions = self._getRawPosition(cmd)
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
                microns = zeroedCnt/self.a_microns_to_microsteps
            elif m == 2:
                microns = zeroedCnt/self.b_microns_to_microsteps
            else:
                microns = zeroedCnt/self.c_microns_to_microsteps

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

    def _getInitString(self, motor):
        """ Get the per-motor motor controller initialization string. """

        # aM%d   - select motor %d
        # n2     - enable limit switches
        # f0     - limit switches are normally closed
        # F0     - positive steps move away from home
        # V%d    - set velocity
        # h%d    - set hold current
        # m%d    - set drive current
        #
        initCmd = "aM%dn2f0F0V%dh%dm%dR"

        return initCmd % (motor, self.velocity, self.holdCurrent, self.runCurrent)

    def initOneArm(self, arm, cmd, doClear=True):
        """ Re-initialize the given arm.

        Args
        ----
          arm : 1..3, a..c
            arm ID
          doClear : bool
            if set, mark the position as unknown.
        """

        armNum = self.armNum(arm)
        m = self.motorNum(arm)
        if doClear:
            self.status[armNum-1] = "Unknown"
            self.positions[armNum-1] = 0

        initCmd = self._getInitString(m)
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(initCmd,
                                                                      cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("Failed to initialize arm %s (motor %d): %s" % (arm, m, errCode))

    def _clearStatus(self, cmd):
        self.status = ["Unknown", "Unknown", "Unknown"]

    def initCcd(self, cmd):
        """ Initialize all CCD motor axes: set scales and limits, etc. """

        self._clearStatus(cmd)

        try:
            for arm in 1,2,3:
                self.initOneArm(arm, cmd)
        finally:
            self.motorStatus(cmd)

    def storePowerOnParameters(self, cmd):
        """ Initialize the boot all CCD motor axes: set scales and limits, etc. """

        s0instruction = "s0e1M500e2M500e3M500R" # controller executes stored programs 1,2, and 3
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
            cmd.inform('text="burning in init commands for motor %d"' % (m))
            try:
                errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(motorParams % (m, initCmd),
                                                                              waitForIdle=True, returnAfterIdle=True,
                                                                              maxTime=3.0, waitTime=1.0,
                                                                              cmd=cmd)
            except RuntimeError as e:
                if not str(e).startswith('no response'):
                    raise
                else:
                    cmd.warn('text="blowing through expected glitch: %s"' % (e))

            if errCode != "OK":
                cmd.fail('text="init of motor %d failed with code=%s"' % (m, errCode))
                return

        cmd.finish()

    def _calcMoveTime(self, distance):
        return distance/self.velocity

    def _moveToSwitch(self, arm, cmd, switch=1, untilClear=True, maxDistance=200,
                      velocity=None, stepping=None):
        """ Move until an arm's switch changes state.

        Args
        ----
          arm : 1..3 or a..c
             The arm ID
          switch : 1 or 2
             Home or far limit switch.
          untilClear : bool
             whether to stop when switch clears or sets.
          maxDistance : int
             how far to move, in full steps.
          velocity : int
             microsteps/sec (default = 10 full steps/s)
          stepping : int
             microsteps (default = 1 full step)
        """

        armNum = self.armNum(arm)
        m = self.motorNum(arm)
        toSet = not untilClear

        if stepping is None:
            stepping = self.microstepping
        if velocity is None:
            velocity = self.microstepping * 10

        motionCmd = "P%d" % stepping if stepping > 0 else "D%d" % -stepping
        moveCmd = "aM%dV%dgS%d%d%d%sG%dR" % (m, velocity,
                                             m, toSet, switch,
                                             motionCmd,
                                             maxDistance)
        try:
            maxTime = self._calcMoveTime(maxDistance) + 0.1*maxDistance + 5.0
            cmd.inform('text="taking arm %s (motor %s) %s %s switch: maxTime=%0.2f"' %
                       (arm, m,
                        "off" if untilClear else "onto",
                        "home" if switch == 1 else "far limit",
                        maxTime))

            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(moveCmd,
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=maxTime,
                                                                          cmd=cmd)
            if errCode != "OK":
                self.haltMotors(cmd, doFinish=False)
                self.status[armNum] = "Unknown"
                self.motorStatus(cmd, doFinish=False)
                cmd.warn('text="arm %d failed with code=%s"' % (arm, errCode))
                return False

            switches = self._getSwitches(arm, cmd)
            if switches[switch-1] != toSet:
                cmd.warn('text="arm %s (motor %d) did not %s %s switch"' % (arm, m,
                                                                            "clear" if untilClear else "set",
                                                                            "home" if switch == 1 else "far limit"))
                return False

        finally:
            self.initOneArm(arm, cmd, doClear=False)
            return True

        return True

    def _setPosition(self, arm, cmd, position):
        """ Define the arm's current position as being at a given step.

        Args
        ----
          arm : 1..3 or a..c
             The arm ID
          position : int
             Full steps for the current position.
        """

        m = self.motorNum(arm)
        moveCmd = "aM%dz%dR" % (m, position*self.microstepping)

        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(moveCmd,
                                                                      waitForIdle=True,
                                                                      returnAfterIdle=True,
                                                                      maxTime=1.0,
                                                                      cmd=cmd)
        if errCode != "OK":
            raise RuntimeError("WTF - could not set current position")

    def toSwitch(self, cmd):
        """ Move until a switch state change
        """

        cmdKeys = cmd.cmd.keywords
        cmd.diag('text="keys: %s"' % (cmdKeys))
        for a in 'a','b','c':
            if a in cmdKeys:
                arm = a
        switch = 1 if 'home' in cmdKeys else 2
        untilClear = 'clear' in cmdKeys
        stepping = self.microstepping

        if (('home' in cmdKeys and 'set' in cmdKeys or
             'far' in cmdKeys and 'clear' in cmdKeys)):
            stepping *= -1

        self._moveToSwitch(arm, cmd, untilClear=untilClear,
                           switch=switch, stepping=stepping)
        self.motorStatus(cmd)

    def homeCcd(self, cmd):
        """ Home CCD motors.

        The arms are homed one after the other, after which they are
        pulled off the home switch. That position is defined to be 100 steps.

        """

        homeCmd1 = "aM%d" + "Z%dR" % (self.homeDistance)

        cmdKeys = cmd.cmd.keywords
        arms = cmdKeys['axes'].values if 'axes' in cmdKeys else ['a','b','c']

        try:
            motors = [self.motorNum(a) for a in arms]
        except KeyError as e:
            cmd.fail('txt="unknown arm name in %r: %s"' % (arms, e))
            return

        # Make sure that the outside world knows that the axis positions are soon to be invalid.
        # There are many failures out of the loop, so declare now.
        self.declareNewMotorPositions(cmd, invalid=True)

        maxTime = self._calcMoveTime(self.homeDistance) + 2.0
        for a_i, arm in enumerate(arms):
            motor = motors[a_i]
            self.status[a_i] = "Homing"
            self.positions[a_i] = 0

            cmd.inform('text="homing arm %s (motor %s): maxTime=%0.2f"' % (arm, motor, maxTime))
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(homeCmd1 % (motor),
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=maxTime,
                                                                          cmd=cmd)
            if errCode != "OK":
                self.haltMotors(cmd, doFinish=False)
                self.status[a_i] = "Unknown"
                self.motorStatus(cmd, doFinish=False)
                cmd.fail('text="home of arm %s (motor %s) failed with code=%s"' % (arm, motor, errCode))
                return
            homeSwitch, _ = self._getSwitches(arm, cmd)
            if not homeSwitch:
                cmd.fail('text="home of arm %s did not leave home switch in."' % (arm))
                return

            cmd.diag('text="home switch for arm %s hit"' % (arm))

        for a_i, arm in enumerate(arms):
            ok = self._moveToSwitch(arm, cmd, switch=1, untilClear=True)
            if ok:
                self.status[a_i] = "OK"
                self._setPosition(arm, cmd, 100)

        self.declareNewMotorPositions(cmd, invalid=False)
        cmd.inform('text="arms homed: %s"' % (arms))

        self.motorStatus(cmd)

    def _moveCcd(self, cmd, a, b, c, absMove):
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
                maxDistance = max(maxDistance, abs(a - self.positions[0]*self.microstepping))
            if b is not None:
                b += self.zeroOffset
                maxDistance = max(maxDistance, abs(b - self.positions[1]*self.microstepping))
            if c is not None:
                c += self.zeroOffset
                maxDistance = max(maxDistance, abs(c - self.positions[2]*self.microstepping))

            cmdChar = 'A'
        else:
            if a is not None:
                maxDistance = max(maxDistance, abs(a))
            if b is not None:
                maxDistance = max(maxDistance, abs(b))
            if c is not None:
                maxDistance = max(maxDistance, abs(c))

            cmdChar = 'P'

        armMoves = (a,b,c)
        motorMoves = self.armOrderToMotorOrder(armMoves)
        motorCmdParts = [int(motorMoves[m_i]) if motorMoves[m_i] is not None else '' for m_i in range(len(motorMoves))]
        cmdStr = "%s%s,%s,%s,R" % (cmdChar, *motorCmdParts)

        maxTime = self._calcMoveTime(maxDistance) + 2.0
        cmd.diag('text="maxDistance=%d maxTime=%0.1f"' % (maxDistance, maxTime))
        try:
            errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd(cmdStr,
                                                                          waitForIdle=True,
                                                                          returnAfterIdle=True,
                                                                          maxTime=maxTime,
                                                                          cmd=cmd)
        except Exception as e:
            errCode = "uncaught error: %s" % (e)

        # Declare that we actually moved, whether or not we succeeded.
        self.declareNewMotorPositions(cmd)

        if errCode != "OK":
            self.haltMotors(cmd, doFinish=False)
            self.motorStatus(cmd, doFinish=False)
            cmd.fail('text="move failed with code=%s"' % (errCode))
        else:
            self.motorStatus(cmd)

    def moveCcd(self, cmd):
        """ Adjust the position of the detector motors.
        Arguments:
            a=num b=num c=num     - one or more motor commands, in ticks.
              or
            piston=num
            abs           - if set, go to absolute position.
            microns       - if set, move in microns (at the FPA) instead of steps.
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
                a = int(float(a) * self.a_microns_to_steps)
            if b is not None:
                b = int(float(b) * self.b_microns_to_steps)
            if c is not None:
                c = int(float(c) * self.c_microns_to_steps)

        self._moveCcd(cmd, a, b, c, absMove)

    def _moveFocus(self, cmd, newFocus):
        """Move to given focus position, applying the tilt calibrations."""

        netMove = newFocus + self.tilts
        netSteps = np.round(netMove * self.microns_to_steps)

        cmd.inform(f'text="moving focus to {newFocus} and {self.tilts} -> {netMove}"')
        self._moveCcd(cmd, *netSteps, absMove=True)

    def moveFocus(self, cmd):
        """Move to given focus position, applying the tilt calibrations and the nominal focus offset. """

        cmdKeys = cmd.cmd.keywords
        moveMicrons = np.array(cmdKeys['microns'].values)
        isAbsolute = 'abs' in cmdKeys

        if not isAbsolute:
            moveMicrons += self.focus
        self._moveFocus(cmd, moveMicrons)

    def haltMotors(self, cmd, doFinish=True):
        errCode, busy, rest = self.actor.controllers['PCM'].motorsCmd('T', cmd=cmd)
        cmd.warn('text="halted motors!"')
        if doFinish:
            cmd.finish()

    def moveToName(self, cmd):
        """ Move to one of the defined special positions: toFocus, toCenter, nearHome, nearFar. """

        cmdKeys = cmd.cmd.keywords
        _axes = ('a','b','c')

        if 'toFocus' in cmdKeys:
            # CPL -- need to load enu to detect med res.
            self._moveFocus(cmd, self.focus)
            return

        moveArgs = dict(cmd=cmd)
        if 'nearHome' in cmdKeys:
            for ax in _axes:
                moveArgs[ax] = self.stepsNearLimit
        elif 'toCenter' or 'nearFar' in cmdKeys:
            far = (self.range * self.microns_to_steps).astype('int')
            if np.any(far <= 0):
                cmd.fail(f'text="far limit position for axis {ax} is not known"')
                return
            for ax_i, ax in enumerate(_axes):
                moveArgs[ax] = (far[ax_i] - self.stepsNearLimit) if 'nearFar' in cmdKeys else far[ax_i]//2
        else:
            raise RuntimeError(f'no known move type for {cmdKeys}')

        moveArgs['absMove'] = True
        self._moveCcd(**moveArgs)
