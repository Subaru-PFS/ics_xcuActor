import logging
import socket
import time

from opscore.utility.qstr import qstr

class rough(object):
    def __init__(self, actor, name,
                 loglevel=logging.INFO):

        self.actor = actor
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

        self.EOL = '\r'
        
        self.host = self.actor.config.get(self.name, 'host')
        self.port = int(self.actor.config.get(self.name, 'port'))

    def start(self):
        pass

    def stop(self, cmd=None):
        pass

    def sendOneCommand(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        fullCmd = "%s%s" % (cmdStr, self.EOL)
        self.logger.info('sending %r', fullCmd)
        cmd.diag('text="sending %r"' % fullCmd)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
        except socket.error as e:
            cmd.warn('text="failed to create socket to rough: %s"' % (e))
            raise
 
        try:
            s.connect((self.host, self.port))
            s.sendall(fullCmd)
        except socket.error as e:
            cmd.warn('text="failed to create connect or send to rough: %s"' % (e))
            raise

        try:
            ret = s.recv(1024)
        except socket.error as e:
            cmd.warn('text="failed to read response from rough: %s"' % (e))
            raise

        self.logger.info('received %r', ret)
        cmd.diag('text="received %r"' % ret)
        s.close()

        return ret

    def parseReply(self, cmdStr, reply, cmd=None):
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
        
        return reply[5:].strip().split(';')
    
    def ident(self, cmd=None):
        cmdStr = '?S801'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startPump(self, cmd=None):
        cmdStr = '!C802 1'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def stopPump(self, cmd=None):
        cmdStr = '!C802 0'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        reply = self.parseReply(cmdStr, ret, cmd=cmd)

        return reply

    def startStandby(self, percent=90, cmd=None):
        cmdStr = "!S805 %d" % (percent)
        ret = self.sendOneCommand(cmdStr, cmd=cmd)

        cmdStr = "!C803 1"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret
    
    def stopStandby(self, cmd=None):
        cmdStr = "!C803 0"
        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        return ret

    def _decodeStatusWord(self, statusWords, statusMsgs):
        """ Convert a list of status words and messages to a bit mask and list of messages.

        Args
        ----
        statusWords : list of 16-bit hex word strings (e.g. "0x107f")
        statusMsgs : n*16 array of strings.
           The messages corresponding to the bits.

        Returns
        -------
        statusBits : int
           The statusWords, converted.
        statusFlags : list of strings
           The Msgs for all set bits.
        
        """
        
        nbits = len(statusWords) * 16
        statusBits = 0
        for i, w in enumerate(statusWords):
            statusBits |= int(w, base=16) << (i*16)

        statusFlags = []
        for i in range(nbits):
            if statusBits & (1 << i) and statusMsgs[i] != '':
                statusFlags.append(statusMsgs[i])

        return statusBits, statusFlags
    
    def decodeStatus(self, statusWords, cmd=None):
        statusMsgs = ('Decelerating',
                      'Running',
                      'Standby speed',
                      'Normal speed',
                      'Above ramp speed',
                      'Above overload speed',
                      '',
                      '',
                      
                      'bit 8',
                      'bit 9',
                      'serial enable',
                      'bit 11',
                      'bit 12',
                      '',
                      'bit 14',
                      'bit 15',
                      
                      'power limit active',
                      'accel. power limited',
                      'decel. power limited',
                      'bit 19',
                      'SERVICE DUE',
                      'bit 21',
                      'WARNING',
                      'ALARM',
                      
                      'bit 24',
                      'bit 25',
                      'bit 26',
                      'bit 27',
                      'bit 28',
                      'bit 29',
                      'bit 30',
                      'bit 31')

        warningMsgs = ('bit 0',
                       'Pump-controller temperature is below the minimum measurable value',
                       'bit 2',
                       'bit 3',
                       'bit 4',
                       'bit 5',
                       'Output current is being restricted due to high pump-controller temperature',
                       'bit 7',
                       'bit 8',
                       'bit 9',
                       'Pump-controller temperature is above the maximum measurable value',
                       'bit 11',
                       'bit 12',
                       'bit 13',
                       'bit 14',
                       'Non-critical problem with EEPROM or other internal function')
        errorMsgs = ('bit 0',
                     'Fault due to excessive link voltage',
                     'Fault due to excessive motor current',
                     'Fault due to excessive pump-controller temperature',
                     'Pump-controller temperature sensor failure',
                     'Power stage failure',
                     'bit 6',
                     'bit 7',
                     'Hardware fault latch active, see bits 0-7 for detail',
                     'Fault due to a critical EEPROM problem (e.g. Parameter upload incomplete)',
                     'bit 10',
                     'Parameter set upload required',
                     'Self test fault (e.g. Invalid software code)',
                     'Fault because the serial enable input went inactive whilst operating with a serial start command',
                     'Fault because the output frequency fell below the threshold for more than the allowable time '
                     '(with an active start command)',  # NOTE: continued string
                     'Fault because the output frequency did not reach the threshold in the allowable time '
                     '(following a start command)')  # NOTE: continued string
        

        statusBits, statusFlags = self._decodeStatusWord(statusWords[0:2], statusMsgs)
        warningBits, warningFlags = self._decodeStatusWord(statusWords[2:3], warningMsgs)
        errorBits, errorFlags = self._decodeStatusWord(statusWords[3:4], errorMsgs)
        
        if warningBits == 0:
            warningFlags = ['OK']
        if errorBits == 0:
            errorFlags = ['OK']
            
        if cmd is not None:
            cmd.inform('roughStatus=0x%08x,%r' % (statusBits,
                                                  ', '.join(statusFlags)))
            warningMsg = 'roughWarnings=0x%04x,%r' % (warningBits,
                                                      ', '.join(warningFlags))
            errorMsg = 'roughErrors=0x%04x,%r' % (errorBits,
                                                  ', '.join(errorFlags))
            if warningBits == 0:
                cmd.inform(warningMsg)
            else:
                cmd.warn(warningMsg)
                
            if warningBits == 0:
                cmd.inform(errorMsg)
            else:
                cmd.warn(errorMsg)
                
        return statusFlags, errorFlags, errorFlags
                 
    def speed(self, cmd=None):
        cmdStr = '?V802'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        status = self.parseReply(cmdStr, ret, cmd=cmd)

        rpm =  int(status[0]) * 60
        status = status[1:]
        
        cmd.inform('roughSpeed=%d' % (rpm))
        self.decodeStatus(status, cmd=cmd)
        
        return rpm, status
        
    def pumpService(self, cmd=None):
        serviceMsgs = ('Tip seal service due',
                       'Bearing service due',
                       'bit 2',
                       'Controller service due',
                       'bit 4',
                       'bit 5',
                       'bit 6',
                       'Service due',
                       'bit 8',
                       'bit 9',
                       'bit 10',
                       'bit 11',
                       'bit 12',
                       'bit 13',
                       'bit 14',
                       'bit 15')
                       
        cmdStr = '?V826'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        status = self.parseReply(cmdStr, ret, cmd=cmd)

        serviceBits, serviceFlags = self._decodeStatusWord(status[0:1],
                                                           serviceMsgs)

        if serviceBits == 0:
            cmd.diag('roughService=0x00,"OK"')
        else:
            cmd.warn('roughService=0x%04x,%r' % (serviceBits, ', '.join(serviceFlags)))

        return serviceFlags
        
    def pumpTemps(self, cmd=None):
        cmdStr = '?V808'

        ret = self.sendOneCommand(cmdStr, cmd=cmd)
        status = self.parseReply(cmdStr, ret, cmd=cmd)

        cmd.inform('roughTemps=%s,%s' % (status[0], status[1]))
        
        return status
        
    def status(self, cmd=None):
        reply = []
        
        speeds = self.speed(cmd=cmd)
        temps = self.pumpTemps(cmd=cmd)
        service = self.pumpService(cmd=cmd)
        reply.extend(speeds)
        reply.extend(temps)
        reply.extend(service)
        
        return reply

    def pumpCmd(self, cmdStr, cmd=None):
        if cmd is None:
            cmd = self.actor.bcast

        ret = self.sendOneCommand(cmdStr, cmd)
        return ret

