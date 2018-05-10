from __future__ import absolute_import

from builtins import object
class Pfeiffer(object):
    def __init__(self):
        self.busID = 1
        
    def parseResponse(self, resp, cmdCode=None, cmd=None):
        """ Fully validate a response telegram, return value

        Args
        ----
        resp : string
          The full, raw response from the gauge
        cmdCode : int/string
          Optionally, the command code that resp is a reply to.
        
        Returns
        -------
        value : string
          The unconverted, but otherwise valid, value string.

        """

        resp = resp.strip()
        try:
            resp = resp.decode('latin-1')
        except AttributeError:
            pass
        
        if len(resp) < 10:
            raise ValueError('response from %s is not long enough: %r' % (self.name,
                                                                          resp))
        try:
            respCrc = int(resp[-3:], base=10)
        except ValueError:
            raise ValueError('response from %s is junk: %r' % (self.name,
                                                               resp))
            
        calcCrc = self.gaugeCrc(resp[:-3])
        if respCrc != calcCrc:
            raise ValueError('response from %s does not have the right CRC (%03d vs %03d): %r' % (self.name,
                                                                                                  respCrc, calcCrc,
                                                                                                  resp))
        if int(resp[:3]) != self.busID:
            raise ValueError('response from %s does not have the right bus ID: %r' % (self.name,
                                                                                      resp))
        if resp[3:5] != '10':
            raise ValueError('response from %s does not have an action of 10 (%s): %r' % (self.name,
                                                                                          resp[3:5],
                                                                                          resp))
        respCode = int(resp[5:8], base=10)
        if cmdCode is not None:
            if respCode != cmdCode:
                raise ValueError('response from %s is not for the expected code (%03d vs. %03d): %r' % (self.name,
                                                                                                        respCode, cmdCode,
                                                                                                        resp))
        valLen = int(resp[8:10], base=10)
        valStr = resp[10:-3]

        if len(valStr) != valLen:
            raise ValueError('value from %s (%r) is not the right length (%d): %r' % (self.name,
                                                                                      valStr, valLen,
                                                                                      resp))
        return valStr
    
    def gaugeCrc(self, s):
        try:
            s = s.encode('latin-1')
        except AttributeError:
            pass
        
        return sum([c for c in s]) % 256

    def gaugeMakeRawCmd(self, cmdStr, cmd=None):
        """ Send set or query string.
        
        Basically, this adds the bus ID, the CRC, and the EOL.

        Args
        ----
        cmdStr : string
          Formatted telegram string. We add the bus ID and the CRC

        Returns
        -------
        raw : string
          The full, unmodified, response from the device. 
        """

        if isinstance(cmdStr, str):
            cmdStr = cmdStr.encode('latin-1')
            
        cmdStr = b'%03d%s' % (self.busID, cmdStr)
        crc = self.gaugeCrc(cmdStr)
        cmdStr = b'%s%03d' % (cmdStr, crc)

        return cmdStr

    def gaugeRawQuery(self, code, cmd=None):
        """ Read a single writable gauge variable.

        Args
        ----
        code : int/str
          One of the commands in section 6.5
          We turn this into a %03d string

        Returns
        -------
        OK - bool
        value - string
           We strip off all but the actual value.
        """
        
        cmdStr = b'00%03d02=?' % (code)
        rawRet = self.gaugeRawCmd(cmdStr, cmd=cmd)
        val = self.parseResponse(rawRet, cmdCode=code, cmd=cmd)

        return val
        
    
    def gaugeRawSet(self, code, value, cmd=None):
        """ Set a single writable gauge variable.

        Args
        ----
        code : int/str
          One of the commands in section 6.5
          We turn this into a %03d string
        value : string
          Some value, sent as is. In other words, you must 
          pad it if necessary.

        Returns
        -------
        Whatever the gauge returns

        """

        #if not isinstance(value, str):
        #    raise TypeError('value must be a string')

        try:
            value = value.encode('latin-1')
        except AttributeError:
            pass
        
        cmdStr = b'10%03d%02d%s' % (code, len(value), value)
        rawRet = self.gaugeRawCmd(cmdStr, cmd=cmd)
        val = self.parseResponse(rawRet, cmdCode=code, cmd=cmd)

        return val
    
    def pressure(self, cmd=None):
        data_out = self.gaugeRawQuery(740, cmd=cmd)

        # 430013 -> 4300 13 -> 4.3e-7
        mantissa = int(data_out[0:4], base=10) * 10.0 ** -3 
        exponent = int(data_out[4:6], base=10) - 20

        # convert to torr
        reading = 0.750061683 * (mantissa * 10**exponent) 

        return reading

