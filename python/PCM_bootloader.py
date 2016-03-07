# Bootloader

import socket as skt
import binascii
import logging
import sys
import time

class PCM_Bootloader(object):
    #------------------------------------------------------------------------------#
    # BOOTLOADER CONSTANTS
    #------------------------------------------------------------------------------#
    # Command Constants
    cLIA_Stat = 0
    cLIA_IP = 1
    cLIA_Invalidate = 2
    cLIA_Capture = 3
    cLIA_Upload = 4
    cLIA_Dump = 5
    cLIA_EraseAll = 6
    cLIA_ErasePgm = 7
    cLIA_EraseEE = 8
    cLIA_Reboot = 9

    # Status Messages
    cLIA_error = 'Error: '
    cLIA_warning = 'Warning: '
    cLIA_message = 'Message: '
    cLIA_debug = 'Debug: '

    cLIA_Status = ([[cLIA_warning, 'A reset vector is required'],
                    [cLIA_message, 'Loader mode set via control port'],
                    [cLIA_warning, 'User code space invalid'],
                    [cLIA_error, 'Loader commnd recieved while not in loader mode'],
                    [cLIA_error, 'New code frame length error'],
                    [cLIA_debug, 'Processed multicast IP packet'],
                    [cLIA_error, 'Record framing error'],
                    [cLIA_warning, 'Unsupported record type'],
                    [cLIA_warning, 'Skipped ID and Config bits'],
                    [cLIA_error, 'Checksum error'],
                    [cLIA_warning, 'Invalid address - Attempt to overwrite loader'],
                    [cLIA_debug, 'Finished programming current record'],
                    [cLIA_debug, 'Finished programming sequence'],
                    [cLIA_message, 'Written to EEprom'],
                    [cLIA_error, 'Missing type 4 record'],
                    [cLIA_message, 'Dump completed']])

    # Miscellaneous Constants
    cLIA_Tag = '5aa5'
    cLIA_Attempts = 4
    cLIA_MCHost = '230.10.10.11'
    cLIA_Port = 16384
    
    def __init__(self, hostname=None,
                 logger='PCM',
                 logLevel=logging.INFO):

        logging.basicConfig(format='%(asctime)s %(message)s')
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logLevel)

        self.LIA_SEQ = 0
        self.LIA_ID = '0000'
        self.LIA_IP = None
        self.hostname = hostname

    #------------------------------------------------------------------------------#
    # BOOTLOADER UTILITIES
    # Used by the bootloader code to communicate with the PCM and parse responses.
    #------------------------------------------------------------------------------#   
    def sendTCPData(self, command, HOST, PORT=1000):
        # send data over TCP
        s = skt.socket(skt.AF_INET, skt.SOCK_STREAM)
        try:
            s.settimeout(2)
            s.connect((HOST, PORT))
            s.settimeout(1)
            s.sendall('%s\r\n' % (command))
            data = s.recv(1024)
            return(data)
        except:
            return 0
        finally:
            if s:
                s.close()

    def newResponse(self):
        resp = dict()
        resp['messages'] = []

    def sendUDPData(self, LIA_CMD, LIA_ID=None, LIA_DATA='', HOST=None, PORT=None):
        # send data over UDP broadcast (unicast optional), and receives unicast response
        # for dump, receive loops until end of dump flag is received
        # returns a dictionary object
        ret = {}
        if LIA_ID == None:
            LIA_ID = self.LIA_ID
        if HOST == None:
            HOST = self.cLIA_MCHost
        if PORT == None:
            PORT = self.cLIA_Port
        header = '%s%s%04x%02x' % (
            self.cLIA_Tag, LIA_ID, self.LIA_SEQ, LIA_CMD)
        header = bytearray.fromhex(header)
        command = '%s%s' % (header, LIA_DATA)
        s = skt.socket(skt.AF_INET, skt.SOCK_DGRAM)
        s.setsockopt(skt.SOL_SOCKET, skt.SO_REUSEADDR, 1)
        #s.setsockopt(skt.SOL_SOCKET, skt.SO_BROADCAST, 1)
        s.setsockopt(skt.SOL_IP, skt.IP_MULTICAST_IF,
                     skt.inet_aton('10.1.1.1'))

        # if HOST==self.cLIA_MCHost:
        # do not route Multicast (i.e. keep on same hop)
        #s.setsockopt(skt.SOL_SOCKET, skt.IP_MULTICAST_TTL,2)
        try:
            if HOST == self.cLIA_MCHost:
                s.bind(('10.1.1.1', 0))  # bind to any IP, any local port
            else:
                s.bind((HOST, 0))  # bind to host IP, any local port
            if LIA_CMD == self.cLIA_EraseAll or LIA_CMD == self.cLIA_ErasePgm or LIA_CMD == self.cLIA_EraseEE:
                s.settimeout(20)  # allow longer for erase to complete
            else:
                s.settimeout(2)
            s.sendto(command, (HOST, PORT))  # send command to taget

            self.logger.debug('send: %s' % (binascii.hexlify(command)))

            raw = s.recv(1024)  # wait to recieve response
            self.logger.debug('recv: %s' % (binascii.hexlify(raw)))
            ret = self.parseLIAResponse(raw)
            dump = ''
            # Loop for file dump only... ret['dump'] will contain dump data
            while (int(ret['cmd']) == int(self.cLIA_Dump) and
                   ret['dumpCompleteFlag'] is False and
                   ret['errorFlag'] is False):
                if dump == '':
                    dump = '%s %s' % (ret['dataSeq'], ret['data'])
                else:
                    dump = '%s\r\n%s %s' % (dump, ret['dataSeq'], ret['data'])
                ret = s.recv(1024)
                self.logger.debug('recv: %s' % (binascii.hexlify(ret)))
                ret = self.parseLIAResponse(ret)

            ret['dump'] = dump
        except:
            self.logger.warn('recv: no response')
            ret['errorFlag'] = True
            ret['messages'].append(self.cLIA_error + 'No response')
        finally:
            if s:
                s.close()
            self.logger.warn(ret['messages'])
        return ret

    def parseLIAResponse(self, LIAdata):
        # creates a dictionary containing each field of the loader response packet
        # checks for errors and appends a status message
        ret = self.newResponse()

        try:
            sRec = binascii.hexlify(LIAdata)
            ret['tag'] = sRec[0:4]
            ret['ID'] = sRec[4:8]
            ret['seq'] = sRec[8:12]
            ret['cmd'] = sRec[12:14]
            ret['pID'] = sRec[14:16]
            ret['HWver'] = sRec[16:18]
            ret['SWver'] = sRec[18:20]
            ret['LIA_ID'] = sRec[20:24]
            ret['IP'] = skt.inet_ntoa(sRec[24:32])
            ret['status'] = sRec[32:36]
            ret['dataSeq'] = sRec[36:38]
            ret['data'] = LIAdata[19:]

            status = self.parseStatusWord(str(ret['status']))

            ret['messages'].append('%s%s%s' % (self.cLIA_message, ret['message'], status['message']))
            ret['errorFlag'] = status['errorFlag']
            ret['warningFlag'] = status['warningFlag']
            ret['dumpCompleteFlag'] = status['dumpCompleteFlag']
            # verify that tag, ID and sequence match
            if ret['tag'] != self.cLIA_Tag:
                msg = 'LIA Tag mismatch: '
                ret['messages'].append('%s%s' % (self.cLIA_error, msg))
                self.errorFlag = True
            if ret['LIA_ID'] != self.LIA_ID:
                msg = 'LIA ID mismatch: %s %s' % (ret['LIA_ID'], self.LIA_ID)
                ret['messages'].append('%s%s' % (self.cLIA_error, msg))
                self.errorFlag = True
            if int(ret['seq'], 16) != int(self.LIA_SEQ):
                msg = 'LIA Sequence mismatch'
                ret['messages'].append('%s%s' % (self.cLIA_error, msg))
                self.errorFlag = True

        except:
            if LIAdata is not None:
                msg = 'Invalid LIA response'
            else:
                msg = 'LIA failed to respond'
            ret['messages'].append('%s%s' % (self.cLIA_error, msg))
            ret['errorFlag'] = True
        return ret

    def parseStatusWord(self, status):
        # returns a status message and status flags
        ret = self.newResponse()
        ret['errorFlag'] = False
        ret['warningFlag'] = False
        ret['dumpCompleteFlag'] = False

        i = 0
        try:
            status = bin(int(status, 16))[2:].zfill(16)
            for bit in status:
                if bit == '1':
                    ret['messages'].append('%s%s' % (self.cLIA_Status[i][0],
                                                     self.cLIA_Status[i][1]))
                    if self.cLIA_Status[i][0] == self.cLIA_error:
                        ret['errorFlag'] = True
                    if self.cLIA_Status[i][0] == self.cLIA_warning:
                        ret['warningFlag'] = True
                i += 1
            if status[15] == '1':
                ret['dumpCompleteFlag'] = True
        except:
            msg = 'Failed to parse status word'
            ret['messages'].append('%s%s' % (self.cLIA_error, msg))
            ret['errorFlag'] = True
        return ret

    def fileWriteLine(self, fname, text):
        f = open(fname, 'a')
        f.writelines(text + '\n')
        f.close()

    def incLIASequence(self):
        # increments the loader sequence number
        self.LIA_SEQ = self.LIA_SEQ + 1
        if self.LIA_SEQ > 65535:
            self.LIA_SEQ = 0

#------------------------------------------------------------------------------#
# BOOTLOADER COMMANDS
# Typical sequence of operation:
#   rebootPCM() ---- puts PCM in discovery mode
#   getLIAStatus() ---- discover PCM
#   enterLDRmode() ---- capture the target and enter Loader mode
#   erasePGMandEE() ---- clears the application space
#   uploadHEXfile() ---- programs the PCM with new firmware
#   exitLDRmode() ---- exits Loader mode and resets the PCM
#
#   Note: the loader use a sequence ID to match commands and responses
#------------------------------------------------------------------------------#

    def rebootPCM(self):
        # forces PCM to reboot when the app is running, allowing bootloader
        # discovery
        cmd = '~reset,sys'
        ret = self.sendTCPData(cmd, self.hostname, 1000)
        self.logger.debug(ret)

        self.logResponse(r)
        
    def getLIAStatus(self):
        # Used to "ping" devices to find PCM's LIA_ID (last 4 of MAC)
        attempts = 0
        success = False
        LIA_CMD = int(self.cLIA_Stat)
        while attempts < self.cLIA_Attempts and success == False:
            ret = self.sendUDPData(LIA_CMD, '0000')
            self.logger.debug(ret)
            if ret['errorFlag'] == True:
                attempts += 1
            else:
                self.LIA_ID = ret['LIA_ID']
                success = True
        self.incLIASequence()
        if success == False:
            self.logger.debug('failed to locate LIA')

        self.logResponse(r)
        
        return ret

    def setLIA_IP(self, IPAddress, LIA_ID=None):
        # can set the LIA bootloader IP (not necessary, but allows unicast)
        LIA_CMD = int(self.cLIA_IP)

        self.LIA_ID = LIA_ID
        IPAddress = skt.gethostbyname(IPAddress)
        hexIP = skt.inet_aton(IPAddress)
        try:
            r = self.sendUDPData(LIA_CMD, LIA_ID, hexIP)
            if r['errorFlag'] is False:
                self.LIA_IP = IPAddress
        except Exception, e:
            r['messages'].append('%s%s: %s' % (self.cLIA_error, 'Invalid Address Format: %s', e))
        self.logger.info('forcing IP address to %s...', IPAddress)

        self.logger.info('forcing IP address to %s...', IPAddress)

        finally:
            self.incLIASequence()

        self.logResponse(r)
        
        return r

    def invalidateLIA(self, LIA_ID=None):
        # marks application as invalid
        LIA_CMD = int(self.cLIA_Invalidate)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        #r = self.parseLIAResponse(r)
        self.logger.debug(r['messages'])
        self.incLIASequence()

        self.logResponse(r)
        
    def enterLDRmode(self, LIA_ID=None):
        self.logger.info('capturing console...')

        # puts PCM into active loader state
        LIA_CMD = int(self.cLIA_Capture)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        self.logger.debug(r['messages'])
        self.incLIASequence()

        self.logResponse(r)
        
        return r

    def uploadHEXfile(self, fileName, LIA_ID=None):
        self.logger.info('starting upload of %s', fileName)

        # uplaods a new hex file (app) to the PCM
        LIA_CMD = int(self.cLIA_Upload)
        try:
            fo = open(fileName, 'r+')
            self.logger.debug('opened %s' % fileName)
            for line in fo.readlines():
                l = str(line).strip()
                if l[0] == ':' and (l[8] == '0' or l[8] == '1' or l[8] == '4'):
                    # only send type 0, 1 or 4 data packets
                    attempts = 0
                    success = False
                    while attempts < self.cLIA_Attempts and success == False:
                        r = self.sendUDPData(LIA_CMD, LIA_ID, l)
                        if r['errorFlag'] == False:
                            success = True
                            attempts = 0
                            self.incLIASequence()
                        else:
                            attempts += 1
                    if not success:
                        print'UPLOAD FAILED'
                        break
            if success:
                self.logger.debug('UPLOAD COMPLETED')
            self.logger.debug(r['messages'])
        except:
            self.logger.debug('Error opening file')
        finally:
            self.incLIASequence()

        self.logResponse(r)
        
        return r

    def dumpHEXfile(self, fileName, LIA_ID=None):
        # dumps hex from device to file
        LIA_CMD = int(self.cLIA_Dump)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        fo = open(fileName, 'wr+')
        i = None
        self.logger.debug(r['dump'])
        for line in r['dump'].split('\r\n'):
            data = line.split(' ')
            if i is None:
                i = int(data[0], 16)
            if int(data[0], 16) != i:
                r['errorFlag'] = True
                r['messages'].append('%s%s' % (self.cLIA_error,
                                               'Error: DataSeq Mismatch'))
                break
            i += 1
            if i > 255:
                i = 0
            self.logger.debug(data)
            try:
                fo.write('%s\n' % (data[1]))
            except:
                pass
        fo.close()
        self.incLIASequence()

        self.logResponse(r)
        
    def erasePGMandEE(self, LIA_ID=None):
        # erases all memory
        LIA_CMD = int(self.cLIA_EraseAll)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        self.incLIASequence()

        self.logResponse(r)
        
        return r

    def erasePGMonly(self, LIA_ID=None):
        # erases program memory
        LIA_CMD = int(self.cLIA_ErasePgm)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        self.incLIASequence()

        self.logResponse(r)
        
    def eraseEEonly(self, LIA_ID=None):
        # erases EEProm (not applicable to PCM)
        LIA_CMD = int(self.cLIA_EraseEE)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        self.incLIASequence()

        self.logResponse(r)
        
    def exitLDRmode(self, LIA_ID=None):
        # causes PCM to exit bootloader and start app
        LIA_CMD = int(self.cLIA_Reboot)
        r = self.sendUDPData(LIA_CMD, LIA_ID)
        self.incLIASequence()

        self.logResponse(r)
        
    def logResponse(self, response):
        """ Transform internal messages into logging messages. """

        lines = response.split('\n')
        for l in lines:
            msg = l
            if response['errorFlag'] or msg.startswith(self.cLIA_error):
                self.logger.error(msg)
            elif response['warningFlag'] or msg.startswith(self.cLIA_warning):
                self.logger.warning(msg)
            elif msg.startswith(self.cLIA_message):
                self.logger.info(msg)
            elif msg.startswith(self.cLIA_debug):
                self.logger.debug(msg)


def burnBabyBurn(args):
    host = args.host
    hexfile = args.hexfile

    pcm = PCM_Bootloader(hostname=host)
    pcm.rebootPCM()
    time.sleep(2)

    ret = pcm.setLIA_IP(host, LIA_ID='6c7d')

    if ret['errorFlag']:
        raise RuntimeError('failed to force IP address: %s' % (ret['messages']))

    ret = pcm.getLIAStatus()
    if ret['errorFlag']:
        raise RuntimeError(
            'failed to find target. returned: %s' % (ret['messages']))
    ret = pcm.enterLDRmode()
    if ret['errorFlag']:
        raise RuntimeError(
            'failed to enter loader mode. returned: %s' % (ret['messages']))
    ret = pcm.erasePGMandEE()
    if ret['errorFlag']:
        raise RuntimeError(
            'failed to erase target. returned: %s' % (ret['messages']))
    ret = pcm.uploadHEXfile(hexfile)
    if ret['errorFlag']:
        raise RuntimeError(
            'failed to program target. returned: %s' % (ret['messages']))


def main(argv=None):
    import argparse

    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, basestring):
        argv = shlex.split()

    parser = argparse.ArgumentParser('Test PCM burning.')
    parser.add_argument('--hexfile', type=str, action='store', default=None,
                        help='the filename of the .hex file')
    parser.add_argument('--host', type=str, action='store', default=None,
                        help='the IP address/name of the PCM board')
    parser.add_argument('--cam', type=str, action='store', default=None,
                        help='the name of the PCM board\'s camera')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(argv)

    burnBabyBurn(args)

if __name__ == "__main__":
    main()
