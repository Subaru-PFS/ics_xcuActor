import logging
import serial
import threading
import time

class interlock(object):
    def __init__(self, actor, name, logLevel=logging.DEBUG):
        self.actor = actor
        self.name = name

        try:
            port = self.actor.config.get(self.name, 'port')
            speed = int(self.actor.config.get(self.name, 'speed'))
        except Exception as e:
            self.actor.bcast.warn('failed to connect to interlock controller: %s' % e)
            raise
            
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logLevel)

        self.device = None
        self.deviceLock = threading.RLock()
        
        self.devConfig = dict(port=port, 
                              baudrate=speed,
                              timeout=1.0)
        self.devConfig['writeTimeout'] = 1.0
        self.EOL = '\n'

        self.connect()

    def __str__(self):
        return ("Interlock(port=%s, device=%s)" %
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

    def sendCommandStr(self, cmdStr, cmd=None):
        if len(cmdStr) > 0 and cmdStr[0] != '~':
            cmdStr = f'~{cmdStr}'
            
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
            if ret != cmdStr:
                raise RuntimeError("command echo mismatch. sent :%r: rcvd :%r:" % (cmdStr, ret))
 
            ret = self.readResponse(cmd=cmd)

        return ret

    def readResponse(self, EOL=None, cmd=None):
        """ Read a single response line, up to the next self.EOL.

        Returns
        -------
        response
           A string, with trailing EOL removed.

        Notes
        -----
        Ignores CRs
        """

        if EOL is None:
            EOL = self.EOL

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
            if c in (EOL, ''):
                break
            response += c

        if cmd is not None:
            cmd.debug('text="recv %r"' % response)
            
        self.logger.debug("received :%r:" % (response))
        return response.strip()

    def setRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        return self.sendCommandStr(cmdStr)

    def sendImage(self, path, verbose=True, doWait=False, sendReboot=True):
        """ Download an image file to the interlock board. 

        For a blank pic (bootloader only), do not send a reboot command.
        Normally, _do_ send a reboot.
        """

        eol = chr(0x0a)
        ack = chr(0x06) # ; ack='+'
        nak = chr(0x15) # ; name='-'
        lineNumber = 1
        maxRetries = 5

        if sendReboot:
            try:
                ret = self.sendCommandStr('reboot')
            except:
                pass
            time.sleep(0.5)
        
            if doWait:
                self.device.timeout = 5
                ret = self.device.readline()
                retline = ret.decode('latin-1').strip()
                self.logger.info('at wait, recv: %r', retline)
                isBootLoader = 'Bootloader' in retline
                if not isBootLoader:
                    raise RuntimeError("not at bootloader prompt (%s)" % (retline))
                isBlank = retline[-1] == 'B'
                self.logger.info('at bootloader: %s (blank=%s), from %r' % (isBootLoader, isBlank, ret))
                if not isBlank:
                    self.logger.info('at bootloader, sending *')
                    self.device.write(b'*')
            else:
                self.logger.info('at bootloader, sending *')
                self.device.write(b'*')

            ret = self.device.readline()
            ret = ret.decode('latin-1').strip()
            self.logger.debug('after * got :%r:', ret)
            if not ret.startswith('*Waiting for Data...'):
                self.logger.info('at bootloader *, got %r' % (ret))
                ret = self.device.readline().decode('latin-1')
                self.logger.debug('after * retry got %r', ret)
                if not ret.startswith('*Waiting for Data...'):
                    raise RuntimeError('could not get *Waiting for Data')

        logLevel = self.logger.level
        # self.logger.setLevel(logging.INFO)
        self.device.timeout = 1.0 # self.devConfig['timeout'] * 100
        strTrans = str.maketrans('', '', '\x11\x13')
        with open(path, 'rU') as hexfile:
            lines = hexfile.readlines()
            t0 = time.time()
            self.logger.info('sending image file %s, %d lines' % (path, len(lines)))
            for l_i, rawl in enumerate(lines):
                hexl = rawl.strip()
                if hexl[0] == ';':
                    continue
                retries = 0
                # self.logger.debug('sending line %d: %r' % (l_i, hexl))
                while True:
                    if verbose and retries > 0:
                        self.logger.warn('resending line %d; try %d' % (lineNumber, 
                                                                        retries))
                    fullLine = hexl+eol
                    if verbose and lineNumber%100 == 1:
                        self.logger.info('sending line %d / %d', lineNumber, len(lines))
                    self.logger.debug("sending line %d: %r", lineNumber, fullLine)
                    if True:
                        retline = self.sendOneLinePerChar(fullLine)
                    else:
                        self.device.write(fullLine.encode('latin-1'))
                        retline = self.device.read(size=len(hexl)+len(eol)+1).decode('latin-1')
                    self.logger.debug('recv %r' % (retline))
                    retline = retline.translate(strTrans)

                    if fullLine != retline[:len(fullLine)]:
                        self.logger.warn("command echo mismatch. sent %r rcvd %r" % (fullLine, retline))
                    ret = retline[-1]
                    lineNumber += 1
                    if ret == ack or hexl == ':00000001FF':
                        break
                    if ret != nak:
                        raise RuntimeError("unexpected response (%r in %r) after sending line %d" %
                                           (ret, retline, lineNumber-1))
                    retries += 1
                    if retries >= maxRetries:
                        raise RuntimeError("too many retries (%d) on line %d" %
                                           (retries, lineNumber-1))

            t1 = time.time()
            
        self.logger.info('sent image file %s in %0.2f seconds' % (path, t1-t0))
        time.sleep(1)
        line = self.device.readline().decode('latin-1')
        self.logger.info('recv: %s', line)
        if 'Bootloader' not in line:
            self.logger.warn('did not get expected Booloader line after loading image (%s)' % line)
        else:
            time.sleep(2)
            line = self.device.readline().decode('latin-1')
            self.logger.info('recv: %s', line)
            if 'Interlock' not in line:
                self.logger.warn('did not get expected Interlock line after loading image (%s)' % line)

        self.logger.setLevel(logLevel)


    def sendOneLinePerChar(self, strline):
        line = strline.encode('latin-1')
        ret = bytearray(len(line) + 1)
        for c_i in range(len(line)):
            c = line[c_i:c_i+1]
            self.device.write(c)
            # time.sleep(0.001)
            retc = self.device.read(1)
            if c != retc:
                raise RuntimeError('boom: mismatch at %d: sent %r but recv %r' % (c_i,c,retc))
            ret[c_i] = retc[0]
        ackNak = self.device.read(1)
        ret[-1] = ackNak[0]

        return ret.decode('latin-1')
    
    
        
            
        
