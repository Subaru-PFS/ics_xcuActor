import logging
import threading

import serial

from opscore.utility.qstr import qstr

class turbo(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.name = name
        self.actor = actor
        self.logger = logging.getLogger('turbo')
        self.logger.setLevel(loglevel)

        self.EOL = '\r'

        port = self.actor.actorConfig[self.name]['port']
        speed = self.actor.actorConfig[self.name]['speed']

        self.device = None
        self.deviceLock = threading.RLock()

        self.devConfig = dict(port=port, 
                              baudrate=speed,
                              timeout=2.0)
        self.connect()

    def __str__(self):
        return ("Turbo(port=%s, device=%s)" %
                (self.devConfig['port'],
                 self.device))
    
    def start(self, cmd=None):
        pass

    def stop(self, cmd=None):
        pass

    def connect(self):
        """ Establish a new connection to the GV interlock. Any old connection is closed.  """

        if self.device:
            self.device.close()
            self.device = None

        self.device = serial.Serial(**self.devConfig)

    def sendOneCommand(self, cmdStr, cmd=None):
        fullCmd = "%s%s" % (cmdStr, self.EOL)
        writeCmd = fullCmd.encode('latin-1')
        with self.deviceLock:
            if cmd is not None:
                cmd.debug('text="sending %r"' % fullCmd)
            self.logger.debug("sending command :%r:" % (fullCmd))
            try:
                self.device.write(writeCmd)
            except serial.writeTimeoutError:
                raise
            except serial.SerialException:
                raise
            except Exception:
                raise

            ret = self.readResponse(cmd=cmd)

        return ret

    def readResponse(self, cmd=None):
        """ Read a single response line, up to the next self.EOL.

        Returns
        -------
        response
           A string, with trailing EOL removed.
        """

        response = ""

        while True:
            try:
                c = self.device.read(size=1)
                # self.logger.debug("received char :%r:" % (c))
            except serial.SerialException:
                raise
            except serial.portNotOpenError:
                raise
            except Exception:
                raise

            c = str(c, 'latin-1')
            if c == '':
                self.logger.warn('pyserial device read(1) timed out')
            if c in (self.EOL, ''):
                break
            response += c

        if cmd is not None:
            cmd.debug('text="recv %r"' % response)
            
        self.logger.debug("received :%r:" % (response))
        return response.strip()

    def parseReply(self, cmdStr, reply, cmd=None):
        if not isinstance(cmdStr, str):
            cmdStr = cmdStr.decode('latin-1')
            
        cmdType = cmdStr[0]

        if cmdType == '?':
            replyFlag = '='
        elif cmdType == '!':
            replyFlag = '*'

        replyStart = reply[:5]
        replyCheck = replyFlag + cmdStr[1:5]
        if not reply.startswith(replyCheck):
            cmd.warn('text=%s' % qstr('reply to command %r is the unexpected %r (vs %r)' % (cmdStr,
                                                                                            replyStart,
                                                                                            replyCheck)))
        
        replyStr = reply[5:].strip().split(';')
        return replyStr

    def ident(self, cmd=None):
        cmdStr = '?S851'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startPump(self, cmd=None):
        # Turn on electronic braking
        # Set at-speed trip point to 98%
        cmds = ['!S872 1',
                '!S856 98']
        for cmdStr in cmds:
            ret = self.sendOneCommand(cmdStr, cmd=cmd)
            reply = self.parseReply(cmdStr, ret, cmd=cmd)

        cmdStr = '!C852 1'
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def stopPump(self, cmd=None):
        cmdStr = '!C852 0'
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startStandby(self, percent=90, cmd=None):
        cmdStr = "!S857 %d" % (percent)
        ret = self.sendOneCommand(cmdStr, cmd=cmd)

        cmdStr = "!C869 1"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret
    
    def stopStandby(self, cmd=None):
        cmdStr = "!C869 0"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret

    def statusWord(self, status, cmd=None):
        flags = ('Fail',
                 'Below stopped speed',
                 'Above normal speed',
                 'Vent valve energized',
                 'Start command active',
                 'Serial enable active',
                 'Standby active',
                 'Above 50% full speed',
                 'Parallel control mode',
                 'Serial control mode',
                 'Invalid podule software',
                 'Podule failed',
                 'Failed to reach speed within timer',
                 'Overspeed or overcurrent tripped',
                 'Pump internal temp. system failure',
                 'Serial enable is inactive',
                 'bit 17',
                 'bit 18',
                 'bit 19',
                 'bit 20',
                 'bit 21',
                 'bit 22',
                 'bit 23',
                 'bit 24',
                 'bit 25',
                 'bit 26',
                 'bit 27',
                 'bit 28',
                 'bit 29',
                 'bit 30',
                 'bit 31')

        allFlags = []
        for i in range(32):
            if status & (1 << i):
                allFlags.append(flags[i])

        if cmd is not None:
            cmd.inform('turboStatus=0x%08x,%r' % (status, ', '.join(allFlags)))

        return allFlags
                 
    def speed(self, cmd=None):
        cmdStr = '?V852'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        speeds = self.parseReply(cmdStr, ret, cmd=cmd)

        rpm =  int(speeds[0]) * 60
        status = int(speeds[1], base=16)
        
        cmd.inform('turboSpeed=%s' % (rpm))
        self.statusWord(status, cmd=cmd)
        
        return rpm, status
        
    def pumpTemps(self, cmd=None):
        cmdStr = '?V859'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        speeds = self.parseReply(cmdStr, ret, cmd=cmd)

        cmd.inform('turboTemps=%s,%s' % (speeds[0], speeds[1]))
        
        return speeds
        
    def pumpVAW(self, cmd=None):
        cmdStr = '?V860'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        pumpStat = self.parseReply(cmdStr, ret, cmd=cmd)

        V, A, W = [float(i) for i in pumpStat]
        V /= 10.0
        A /= 10.0
        W /= 10.0

        if cmd is not None:
            cmd.inform('turboVAW=%g,%g,%g' % (V,A,W))
            
        return V,A,W
        
    def status(self, cmd=None):
        reply = []
        
        speeds = self.speed(cmd=cmd)
        VAW = self.pumpVAW(cmd=cmd)
        temps = self.pumpTemps(cmd=cmd)
        reply.extend(speeds)
        reply.extend(VAW)
        reply.extend(temps)
        
        return reply

    def pumpCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

