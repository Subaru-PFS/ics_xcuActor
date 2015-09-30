#!/usr/bin/env python

import numpy as np

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TempsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('temps', '@raw', self.tempsRaw),
            ('temps', 'flash <filename>', self.flash),
            ('temps', 'status', self.status),
            ('temps', 'test1', self.test1),
            ('temps', 'test2', self.test2),
            ('HPheaters', '@(on|off) @(one|two)', self.HPheaters),
            ('heaters', '@(ccd|spider) <power>', self.heatersOn),
            ('heaters', '@(ccd|spider) @off', self.heatersOff),
            ('heaters', 'status', self.heaterStatus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_temps", (1, 1),
                                        keys.Key("filename", types.String(),
                                                 help='filename to read or flash'),
                                        keys.Key("power", types.Int(),
                                                 help='power level to set (0..100)'),
                                        )

    def tempsRaw(self, cmd):
        """ Send a raw command to the temps controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['temps'].tempsCmd(cmd_txt, cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    def heaterStatus(self, cmd):
        self.actor.controllers['temps'].fetchHeaters(cmd=cmd)
        cmd.finish()
        
    def heatersOn(self, cmd):
        """ Turn one of the heaters on. """

        cmdKeys = cmd.cmd.keywords

        power = cmdKeys['power'].values[0]

        if 'spider' in cmdKeys:
            heater = 'spider'
        elif 'ccd':
            heater = 'ccd'
        else:
            cmd.fail('text="no heater (ccd or spider) was specified!"')
            return

        try:
            self.actor.controllers['temps'].heater(turnOn=True,
                                                   heater=heater,
                                                   power=power,
                                                   cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))
            return

        cmd.finish()

    def heatersOff(self, cmd):
        """ Turn one of the heaters off. """

        cmdKeys = cmd.cmd.keywords

        if 'spider' in cmdKeys:
            heater = 'spider'
        elif 'ccd':
            heater = 'ccd'
        else:
            cmd.fail('text="no heater (ccd or spider) was specified!"')
            return

        try:
            self.actor.controllers['temps'].heater(turnOn=False,
                                                   heater=heater,
                                                   power=0,
                                                   cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))
            return

        cmd.finish()

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

        if 'one' in cmdKeys:
            heater = 1
        elif 'two' in cmdKeys:
            heater = 2
        else:
            cmd.fail('text="no heater (legs or base) was specified!"')
            return

        try:
            self.actor.controllers['temps'].HPheater(turnOn=turnOn,
                                                     heaterNum=heater,
                                                     cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to control heaters: %s"' % (e))
            return

        cmd.finish()

    def flash(self, cmd):
        """ Flash the temperatire board with new firmware. """
        
        filename = cmd.cmd.keywords['filename'].values[0]
        try:
            self.actor.controllers['temps'].sendImage(filename, cmd=cmd)
        except Exception as e:
            cmd.fail('text="failed to flash from %s: %s"' % (filename, e))
            return

        cmd.finish('text="flashed from %s"' % (filename))
            
    def status(self, cmd, doFinish=True):
        """ Return all status keywords. """
        
        temps = self.actor.controllers['temps'].fetchTemps(cmd=cmd)
        ender = cmd.finish if doFinish else cmd.inform
        ender('temps=%s' % ', '.join(['%0.2f' % (t) for t in temps]))

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
                
        
            
        
