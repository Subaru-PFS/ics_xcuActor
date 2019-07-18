#!/usr/bin/env python

from __future__ import division
from builtins import range
from builtins import object
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
            # ('pcm', 'status [@(clear)]', self.udpStatus),       
            ('power', '@(on|off|cycle) @(motors|gauge|cooler|temps|bee|fee|interlock|heaters|all) [@(force)]', self.nPower),
            # ('power', '@(on|off) @(motors|gauge|cooler|temps|bee|fee|interlock|heaters|all) [@(force)]', self.power),
            ('power', '@(voltage|current) @(ups|aux|motors|gauge|cooler|temps|bee|fee|interlock|heaters|all) [<n>] [@(counts)]',
             self.getPower),
            ('power', '@(status)', self.getPowerStatus), 
            ('pcm', '@(calibrate) @(voltage|current|environment) @(ups|aux|motors|gauge|cooler|temps|bee|fee|interlock|heaters|temperature|pressure) <r1> <m1> <r2> <m2>',
             self.calibrateChannel), 
            ('pcm', '@(saveCalData)', self.saveCalDataToROM),            
            ('pcm', '@(environment) @(temperature|pressure|all)', self.getEnvironment),
            ('pcm', 'status', self.getPCMStatus),
            ('pcm', '@(reset) @(ethernet|system) [@(force)]', self.resetPCM),
            ('pcm', '@(setMask) @(powerOn|lowVoltage) <mask>', self.setMask),
            ('pcm', '@(getMask) @(powerOn|lowVoltage)', self.getMask),
            ('pcm', '@(getThreshold) @(upsBattery|upsLow|auxLow)', self.getThreshold),
            ('pcm', '@(setThreshold) @(upsBattery|upsLow|auxLow) <v>', self.setThreshold),
            ('pcm', '@(bootload) <filename>', self.bootloader),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_pcm", (1, 1),
                                        keys.Key("n", types.Int(),
                                                 help='number of samples'),
                                        keys.Key("m1", types.Float(),
                                                 help='measured value 1 (low)'),
                                        keys.Key("m2", types.Float(),
                                                 help='measured value 2 (high)'),
                                        keys.Key("r1", types.Float(),
                                                 help='raw count 1 (low)'),   
                                        keys.Key("r2", types.Float(),
                                                 help='raw count 2 (low)'), 
                                        keys.Key("mask", types.String(),
                                                 help='mask value, 8 bit binary string'),
                                        keys.Key("v", types.Float(),
                                                 help='thershold voltage'), 
                                        keys.Key("filename", types.String(),
                                                 help='new firmware file name'),
                                        )


    def pcmRaw(self, cmd):
        """ Send a raw command to the PCM controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.actor.controllers['PCM'].pcmCmd(cmd_txt, cmd=cmd)
        cmd.finish('text="returned %r"' % (ret))

    def udpStatus(self, cmd):
        """ Force generation of the UDP keywords which we most care about. """

        clear = 'clear' in cmd.cmd.keywords

        self.actor.controllers['pcmUdp'].status(cmd=cmd)

        if clear:
            self.actor.controllers['pcmUdp'].clearKeys()
            
        cmd.finish()

    def getParameterName(self, x):
        return {
            'ups': 'bus0',
            'aux': 'bus1',
            'all': 'all',
            'motors': 'ch1',
            'gauge': 'ch2',
            'cooler': 'ch3',
            'temps': 'ch4',
            'bee': 'ch5',
            'fee': 'ch6',
            'interlock': 'ch7',
            'heaters': 'ch8',
            'temperature': 'temp',
            'pressure': 'pres',
        }.get(x)     

    def nPower(self, cmd):
        """ Power some PCM components on or off.

        Arguments:
           on/off    - one of the two.
           name      - one subsystem to power on/off.
           force               
        """
        cmdKeys = cmd.cmd.keywords
        
        portName = self.getParameterName(cmdKeys[1].name)        
        if portName == None:
            cmd.fail('text="invalid port specified"') 
            return
        
        if 'on' in cmdKeys:
            portState = 'on'
        elif 'off' in cmdKeys:
            portState = 'off'
        elif 'cycle':
            portState = 'cycle'
        else:
            cmd.fail('text="neither on nor off was specified!"')
            return
        
        if (portState == 'off' or portState == 'cycle') and ('bee' in cmdKeys or 'all' in cmdKeys):
            if 'force' not in cmdKeys:
                cmd.fail('text="You must specify force if you want to turn the bee off"')
                return
        
        cmdStr = "~se,%s,%s" % (portName, portState)   
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret is None:
            cmd.fail('text="failed to execute power command"')
            return

        self.getPowerStatus(cmd)

    def getPower(self,cmd):
        """ Request port voltages or current

        Arguments:
           type      - voltage or current
           name      - one subsystem to read voltage/current or all
           n         - optional, number of of samples
           counts    - optional, read raw ADC counts
        """
        cmdKeys = cmd.cmd.keywords
        portName = self.getParameterName(cmdKeys[1].name) 
        if portName == None:
            cmd.fail('text="invalid port specified"') 
            return
        if 'n' in cmdKeys:
            n=cmdKeys['n'].values[0]
        else: 
            n=1  
        if 'counts' in cmdKeys:
            r='rawData'
        else:
            r=None
        if 'voltage' in cmdKeys:    
            cmdStr = "~rdV,%s,%d,%s" % (portName,n,r)
        elif 'current' in cmdKeys:
            cmdStr = "~rdC,%s,%d,%s" % (portName,n,r) 
        else:
            cmd.fail('text="must specify voltage or current"') 
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to execute power command"')
            return
        cmd.finish('text="returned %r"' % (ret))
        
    def getPowerState(self, cmd, doFinish=True):
        """ Request power port status. Always reports on all ports.  """
        
        cmdKeys = cmd.cmd.keywords
        
        r = cmdKeys['counts'] if 'counts' in cmdKeys else None
        n = cmdKeys['n'] if 'n' in cmdKeys else 1

        cmdStr = "~rdV,%s,%d,%s" % ('all',n,r)
        rawVolts = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        cmdStr = "~rdC,%s,%d,%s" % ('all',n,r)
        rawAmps = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)

        volts = [float(v) for v in rawVolts.split(b',')]
        amps = [float(a) for a in rawAmps.split(b',')]
        states = [c for c in self.actor.controllers['PCM'].pcmCmd('~ge', cmd=cmd).decode('latin-1')]

        cmd.diag('text="states: %s"' % (states))

        inputNames = ["24Vups", "24Vaux"]
        for nidx in range(2):
            lineState = "OK" # figure out battery power, etc later.
            cmd.inform('pcmPower%d=%s,%s,%0.3f,%0.3f,%0.3f' %
                       (nidx+1, inputNames[nidx],
                        lineState,
                        volts[nidx], amps[nidx],
                        volts[nidx]*amps[nidx]))
            
        rawPortNames = self.actor.config.get('pcm', 'portNames')
        portNames = [s.strip() for s in rawPortNames.split(',')]

        for nidx in range(len(portNames)):
            cmd.inform('pcmPort%d="%s","%s",%0.2f,%0.2f,%0.2f' %
                       (nidx+1, portNames[nidx],
                        states[-(nidx+1)],
                        volts[nidx+2],
                        amps[nidx+2],
                        volts[nidx+2]*amps[nidx+2]))

        if doFinish:
            cmd.finish()
        
    def getEnvironment(self, cmd):
        """ Request PCM environment

        Arguments:
           name      - temperature, pressure or all
        """
        cmdKeys = cmd.cmd.keywords
        paramName = self.getParameterName(cmdKeys[1].name) 
        if paramName == None:
            cmd.fail('text="invalid port specified"') 
            return
            
        cmdStr = "~rdEnv,%s" % (paramName)
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to execute environment command"')
            return
        cmd.finish('text="returned %r"' % (ret))    
     
    def getPCMStatus(self, cmd):
        """ Request status

        Arguments:
           none.
        """
    
            
        cmdStr = "~gStatus"
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to execute getStatus command"')
            return
        cmd.finish('text="returned %r"' % (ret))
   
    def getPowerStatus(self, cmd):
        """ Request status

        Arguments:
           none.
        """
      
        cmdStr = "~ge"
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret is None:
            cmd.fail('text="failed to execute getStatus command"')
            return
        binVal = self.powerMasktoInt(ret)
        cmd.inform("powerMask=0x%02x; poweredUp=%s" % (binVal,
                                                       self.getPoweredNames(binVal)))    
        self.getPowerState(cmd)
        

    def resetPCM(self, cmd):
        """ Reset PCM or Ethernet

        Arguments:
           system | ethernet      - specify what to reset
           [force]                - force required for system reset
        """

        cmdKeys = cmd.cmd.keywords
            
        if 'ethernet' in cmdKeys:
            device='eth'
        elif 'system' in cmdKeys:
            if 'force' in cmdKeys:
                device='sys'
            else:
                cmd.fail('text="must specify force to reset PCM"')
                return
        else:
           cmd.fail('text="must specify ethernet or system"')  
           return
            
        cmdStr = "~reset,%s" % (device)
        self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        cmd.finish()  
        
    def calibrateChannel(self, cmd):
        
        cmdKeys=cmd.cmd.keywords
        
        measurementType = cmdKeys[1].name   
        if measurementType==None:
            cmd.fail('text="invalid measurement type specified')
            return
        
        measurementChannel= self.getParameterName(cmdKeys[2].name)       
        if measurementChannel==None:
            cmd.fail('text="invalid channel specified"')
            return
        elif measurementType=='voltage' or measurementType=='current':
            if measurementChannel=='pres' or measurementChannel=='temp':
                cmd.fail('text="invalid channel specified"')
                return    
        elif measurementType=='environment':
            if measurementChannel !='pres' and measurementChannel !='temp':
                cmd.fail('text="invalid channel specified"')
                return
        
        m1=cmdKeys['m1'].values[0]  # measured value in engineering units
        m2=cmdKeys['m2'].values[0]  
        r1=cmdKeys['r1'].values[0]  #raw value in counts
        r2=cmdKeys['r2'].values[0]
        
        if r1==None or r2==None or m1==None or m2==None:
            cmd.fail('text="missing parameters"')
            return
        dy = m2-m1
        dx = r2-r1
        if dx==0 or dy==0:
            cmd.fail('text="invalid calibration data, check m1,m2,r1,r2 values"')
            return
        m=dy/dx # m is the slope (y=mx+c) --- rise/run
        c=(m*r1)-m1 # c is the offset
        
        if measurementType == 'voltage':
            cmdStr="~calV,%s,%f,%f" % (measurementChannel,c,m)
        elif measurementType == 'current':
            cmdStr="~calC,%s,%f,%f" % (measurementChannel,c,m)
        else:
            cmdStr="calEnv,%s,%f,%f" % (measurementChannel,c,m)
            
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to execute %r calibration on %r channel"' % (cmdKeys[1].name, cmdKeys[2].name))
            return
        cmd.finish('text="returned %r"' % (ret))       

    def saveCalDataToROM(self,cmd):   
        
        cmdStr ="~sCal"
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to save calibration"')
            return
        cmd.finish('text="returned %r"' % (ret)) 
        
    def getMask(self,cmd):
        
        cmdKeys=cmd.cmd.keywords
       
        maskID = cmdKeys[1].name
                
        if maskID =='powerOn':
            mID='boot'
        elif maskID == 'lowVoltage':
            mID='low'
        else:    
            cmd.fail('text="invalid mask id"')
            return
    
        cmdStr ="~gMask,%s" % (mID)
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to get the %r mask"' % (maskID))
            return
        cmd.finish('text="returned %r"' % (ret))  
        
        
    def setMask(self,cmd):  
    
        cmdKeys=cmd.cmd.keywords
           
        maskID = cmdKeys[1].name
        mask = cmdKeys['mask'].values[0]
                
        if maskID =='powerOn':
            mID='boot'
        elif maskID == 'lowVoltage':
            mID='low'
        else:    
            cmd.fail('text="invalid mask id"')
            return
    
        if len(mask) !=8:
            cmd.fail('text="mask length must be 8 characters"')
            return
        for i in range(0, len(mask)):
            if mask[i] !='0':
                if mask[i] !='1':
                    cmd.fail('text="mask can only contain 1 or 0 characters"')
                    return
            
        cmdStr ="~sMask,%s,%s" % (mID,mask)
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to set the %r mask"' % (maskID))
            return
        cmd.finish('text="returned %r"' % (ret)) 
     
    def getThreshold(self,cmd):
       
        cmdKeys=cmd.cmd.keywords
           
        thresholdID = cmdKeys[1].name
                
        if thresholdID =='upsBattery':
            tID='batt'
        elif thresholdID == 'upsLow':
            tID='low'
        elif thresholdID == 'auxLow':
            tID='auxLow'
        else:    
            cmd.fail('text="invalid threshold id"')
            return       
        
        cmdStr="~gThr,%s" % (tID)    
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to get the %r threshold"' % (thresholdID))
            return
        cmd.finish('text="returned %r"' % (ret))     
     
    def setThreshold(self,cmd):
       
        cmdKeys=cmd.cmd.keywords
           
        thresholdID = cmdKeys[1].name
        voltage = cmdKeys['v'].values[0]
                
        if thresholdID =='upsBattery':
            tID='batt'
        elif thresholdID == 'upsLow':
            tID='low'
        elif thresholdID == 'auxLow':
            tID='auxLow'
        else:    
            cmd.fail('text="invalid threshold id"')
            return       
        
        if voltage >30 or voltage < 0:
            cmd.fail('text="threshold must be between 0 and 30 volts"')
            return
        
        cmdStr="~sThr,%s,%f" % (tID,voltage)    
        ret = self.actor.controllers['PCM'].pcmCmd(cmdStr, cmd=cmd)
        if ret == None:
            cmd.fail('text="failed to set the %r mthreshold"' % (thresholdID))
            return
        cmd.finish('text="returned %r"' % (ret))

    def bootloader(self, cmd):
        return
        
    def powerMasktoInt(self,mask):
        for n in mask:
            if n != 1:
                n=0
        return int(mask[2:],2)

    def systemInPowerMask(self, mask, system):
        pcm = self.actor.controllers.get('PCM', None)
        return pcm.systemInPowerMask(mask, system)
    
    def getPoweredNames(self, mask):
        """ Return a list of names of the powered ports. """
    
        mask = int(mask)
        
        ports = []
        pcm = self.actor.controllers.get('PCM', None)
        for i in range(8):
            if mask & (1 << i):
                if pcm is None:
                    ports.append("p%d" % (i+1))
                else:
                    ports.append(pcm.powerPorts[i])
    
        portStr = ','.join(['"%s"' % p for p in ports])
        return portStr    

    def power(self, cmd):
        """ Power some PCM components on or off.

        Arguments:
           on/off    - one of the two.
           name      - one subsystem to power on/off.
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


