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

        return resp
    
    def makeRawCmd(self, cmdStr, cmd=None):
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

        cmdStr = b'%%%d%s' % (self.busID, cmdStr)

        return cmdStr

    def makePressureCmd(self):
        return self.makeRawCmd('rVac,torr')
    
    def parsePressure(self, rawReading):
        return float(rawReading)
    
        # 430013 -> 4300 13 -> 4.3e-7
        mantissa = int(rawReading[0:4], base=10) * 10.0 ** -3 
        exponent = int(rawReading[4:6], base=10) - 20

        # convert to torr
        reading = 0.750061683 * (mantissa * 10**exponent) 

        return reading

