#!/usr/bin/env python

import logging

import numpy as np

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TempsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.logger = logging.getLogger('temps')

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('temps', '@raw', self.tempsRaw),
            ('temps', 'status [<channel>]', self.getTemps),
            ('temps', 'test1', self.test1),
            ('temps', 'test2', self.test2),
            ('HPheaters', '@(on|off) @(shield|spreader)', self.HPheaters),
            ('heaters', '@(ccd|h4|asic) <power>', self.heaterToPower),
            ('heaters', '@(ccd|h4|asic) <temp>', self.heaterToTemp),
            ('heaters', '@(ccd|h4|asic) @centerOffset', self.centerOffset),
            ('heaters', '@config @(ccd|h4|asic) [<P>] [<I>] [<sensor>] [<safetyBand>]', 
             self.heaterConfigure),
            ('heaters', '@(ccd|h4|asic) @off', self.heaterOff),
            ('heaters', 'status', self.heaterStatus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_temps", (1, 1),
                                        keys.Key("power", types.Int(),
                                                 help='power level to set (0..100)'),
                                        keys.Key("temp", types.Float(),
                                                 help='temp setpoint (K)'),
                                        keys.Key("channel", types.Int(),
                                                 help='channel to read'),
                                        keys.Key("P", types.Float(),
                                                 help='Proportional gain'),
                                        keys.Key("I", types.Float(),
                                                 help='Integral gain'),
                                        keys.Key("safetyBand", types.Float(),
                                                 help='temperature margin to keep above coldest sensor.'),
                                        keys.Key("sensor", types.Int(),
                                                 help='sensor to servo on. 1..12'),
                                          
                                        )

    def tempsRaw(self, cmd):
        """ Send a raw command to the temps controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['temps'].tempsCmd(cmd_txt, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    def getTemps(self, cmd, doFinish=True):
        
        try:
            channelID = int(cmd.cmd.keywords['channel'].values[0])
        except:
            channelID = None
        
        if channelID is None:
            cmdStr = "?t"
        elif channelID<1 or channelID>12:
            cmd.fail('text="invalid cahnnel specified"')
        else:
            cmdStr = "?K%d" % (channelID)
        ret = self.actor.controllers['temps'].tempsCmd(cmdStr, cmd=cmd) 

        if channelID is None:
            ender = cmd.finish if doFinish else cmd.inform
            temps = ret.split(',')
            if self.actor.ids.arm in 'brm':
                # Was 0,1,2,... See INSTRM-1147
                # had to actually change actorkeys ordering
                visTemps = [temps[i] for i in (0,1,2,3,4,10,11)]
                cmd.inform('visTemps=%s' % ', '.join(['%0.4f' % (float(t)) for t in visTemps]))
            elif self.actor.ids.specNum <= 4:  # Ignore disgusting wiring in JHU test dewars (n8, n9).
                nirTemps = [temps[i] for i in (1,0,2,3,4,5,7,8,9,10,11)]
                cmd.inform('nirTemps=%s' % ', '.join(['%0.4f' % (float(t)) for t in nirTemps]))
            ender('temps=%s' % ', '.join(['%0.4f' % (float(t)) for t in temps]))
        else:
            cmd.finish('text="returned %r"' % (ret))

    @property
    def heaterNamesForCamera(self):
        """Fetch the list of heater names for the current camera."""
        if self.actor.ids.arm == 'n':
            return ['asic', 'h4']
        else:
            return ['ccd']

    @property
    def heaterListForCamera(self):
        """Fetch the list of heaters (id, name) for the current camera."""
        if self.actor.ids.arm == 'n':
            return [(1, 'asic'), (2, 'h4')]
        else:
            return [(2, 'ccd')]

    def heaterIdForName(self, name):
        """Return the heater id for the given name."""
        for hid, hname in self.heaterListForCamera:
            if hname == name:
                return hid
        return None
    
    def parseHeaterReply(self, rawReply, cmd):
        d = dict()
        for p in rawReply.split():
            k, v = p.split('=')
            if '.' in v:
                v = float(v)
            else:
                v = int(v)
            d[k] = v
        return d

    heaterModes = {0: 'OFF', 1: 'POWER', 3: 'TEMP', 4: 'SAFETY'}
    
    def heaterStatus(self, cmd):
        self.actor.controllers['temps'].fetchHeaters(cmd=cmd)

        for hid, hname in self.heaterListForCamera:
            rawReply = self.actor.controllers['temps'].tempsCmd(f'heater status id={hid}',
                                                                cmd=cmd)
            d = self.parseHeaterReply(rawReply, cmd)
            mode = self.heaterModes[d['mode']]
            output = d['output']
            temp = d['temp']
            level = min(1.0, output/0.096)
            levelSetPoint = level if mode == 'POWER' else 0.0
            tempsSetPoint = d['setpoint'] if mode == 'TEMP' else 0.0
                
            cmd.inform(f'heater{hid}={hname},{mode},{tempsSetPoint:0.2f},{levelSetPoint:0.2f},{level:0.3f},{temp:0.04f}')
        cmd.finish()

    def getValidHeater(self, cmd):
        """ Return the name and id of a valid heater in the command args."""
        cmdKeys = cmd.cmd.keywords
        validNames = self.heaterNamesForCamera

        for n in validNames:
            if n in cmdKeys:
                return n, self.heaterIdForName(n)
        raise ValueError(f'no valid heater ({validNames}) was specified!')

    def heaterToTemp(self, cmd):
        """ Make one of the heaters servo to a given temperature. """

        cmdKeys = cmd.cmd.keywords

        heaterName, heaterId = self.getValidHeater(cmd)
        setpoint = cmdKeys['temp'].values[0]

        mode = 'TEMP' if setpoint > 0.0 else 'IDLE'
        try:
            self.actor.controllers['temps'].tempsCmd(f'heater configure id={heaterId} setpoint={setpoint} mode={mode}',
                                                      cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))

        self.heaterStatus(cmd)

    def heaterToPower(self, cmd):
        """ Set one of the heaters to a given power level  """

        cmdKeys = cmd.cmd.keywords

        heaterName, heaterId = self.getValidHeater(cmd)
        setpoint = cmdKeys['power'].values[0] / 100.0

        mode = 'POWER' if setpoint > 0.0 else 'IDLE'
        try:
            self.actor.controllers['temps'].tempsCmd(f'heater configure id={heaterId} power={setpoint} mode={mode}',
                                                      cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))

        self.heaterStatus(cmd)

    def centerOffset(self, cmd):
        """ Set the centerOffset for one of the heaters. """

        heaterName, heaterId = self.getValidHeater(cmd)

        try:
            self.actor.controllers['temps'].tempsCmd(f'heater centerOffset id={heaterId}',
                                                      cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))

        self.heaterStatus(cmd)
        
    def heaterOff(self, cmd):
        """ Turn one of the heaters off. """

        heaterName, heaterId = self.getValidHeater(cmd)
        if heaterName is None:
            return

        try:
            self.actor.controllers['temps'].tempsCmd(f'heater configure id={heaterId} mode=idle',
                                                      cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))

        self.heaterStatus(cmd)

    def heaterConfigure(self, cmd):
        """ Configure one of the heaters. """

        cmdKeys = cmd.cmd.keywords

        heaterName, heaterId = self.getValidHeater(cmd)
        if heaterName is None:
            return

        terms = []
        for arg in 'P', 'I', 'sensor', 'offset', 'safetyBand':
            if arg in cmdKeys:
                terms.append(f'{arg}={cmdKeys[arg].values[0]}')
        if not terms:
            cmd.fail('text="no configuration terms were specified!"')
            return

        try:
            cmdStr = f'heater configure id={heaterId} {" ".join(terms)}'
            self.actor.controllers['temps'].tempsCmd(cmdStr, cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to configure heater {heaterName}: %s"' % (e))

        self.heaterStatus(cmd)

    def HPheaters(self, cmd):
        """ Control the heaters. """

        cmdKeys = cmd.cmd.keywords

        if 'on' in cmdKeys:
            turnOn = True
        elif 'off' in cmdKeys:
            turnOn = False
        else:
            cmd.fail('text="neither on nor off was specified!"')
            return

        if 'shield' in cmdKeys:
            heater = 1
        elif 'spreader' in cmdKeys:
            heater = 2
        else:
            cmd.fail('text="no heater (shield or spreader) was specified!"')
            return

        try:
            self.actor.controllers['temps'].HPheater(turnOn=turnOn,
                                                     heaterNum=heater,
                                                     cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))
            return

        cmd.finish()

    def status(self, cmd, doFinish=True):
        """ Return all status keywords. """
        
        temps = self.actor.controllers['temps'].fetchTemps(cmd=cmd)
        ender = cmd.finish if doFinish else cmd.inform
        ender('temps=%s' % ', '.join(['%0.4f' % (t) for t in temps]))

        return temps
    
    def test2(self, cmd):
        """Test readings against dewar feedthrough test pack. 

        This checks that the temperature board readings are within 0.5K of the reference values,
        and that the cooler tip value is 0.5K of its reference value. 

        The test expects all four test resistor packs -- T3, T4, T6,
        and T7 -- to be installed in the corresponding feedthrough
        headers inside the dewar.
        """

        testPoints = dict(JP4=(5,6,7),
                          JP6=(4,'tip'),
                          JP7=(1,2,3),
                          JP3=(8,9,10,11,12))

        # These are the readings from the single test pack.
        testData = [146.26,158.59,174.96,188.48,208.43,225.06,252.95,284.05,298.16,321.68,348.23,403.70]
        coolerTestData = 272.36
        
        try:
            temps = self.status(cmd=cmd, doFinish=False)
        except Exception as e:
            cmd.fail('text="Failed to read test2 sensors: %s"' % (e))
            return

        errs = []
        tdAll = np.array(testData) - np.array(temps)
        for i, td1 in enumerate(tdAll):
            if np.abs(td1) >= 0.5:
                errs.append('sensor%d: read=%0.2f, ref=%0.2f' % (i+1, temps[i], testData[i]))

        try:
            coolerStat = self.actor.controllers['cooler'].status(cmd=cmd)
            coolerTemp = coolerStat[-2]
            if abs(coolerTemp - coolerTestData) >= 0.5:
                errs.append('coolerTip: read=%0.2f, ref=%0.2f' % (coolerTemp, coolerTestData))
        except Exception as e:
            errs.append('failed to read cooler: %s' % (e))

        if errs:
            for e in errs:
                cmd.warn('text="test2 error: %s"' % (e))
            cmd.fail('text="temperature test2 failed"')
        else:
            cmd.finish('text="temperature test2 OK"')
                
    def test1(self, cmd):
        """Test readings against pie pan test pack. 

        This checks that the temperature board readings are within 0.5K of the reference values.

        The test requires that the T11 resistor pack to be installed
        in JP11 on the back of the pie pan.
        """

        # These are the readings from the single test1 pack.
        testData = [474.84,434.26,396.66,347.96,317.79,295.26,286.63,248.27,228.53,210.77,192.77,174.80]
        
        try:
            temps = self.status(cmd=cmd, doFinish=False)
        except Exception as e:
            cmd.fail('text="Failed to read test1 sensors: %s"' % (e))
            return

        errs = []
        tdAll = np.array(testData) - np.array(temps)
        for i, td1 in enumerate(tdAll):
            if np.abs(td1) >= 0.5:
                errs.append('sensor%d: read=%0.2f, ref=%0.2f' % (i+1, temps[i], testData[i]))

        if errs:
            for e in errs:
                cmd.warn('text="test1 error: %s"' % (e))
            cmd.fail('text="temperature test1 failed"')
        else:
            cmd.finish('text="temperature test1 OK"')
                
        
            
        
