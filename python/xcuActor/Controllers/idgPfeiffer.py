class Pfeiffer(object):
    def __init__(self, name):
        self.busID = 1
        self.name = name

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

        Basically, this adds the bus ID and the EOL.

        Args
        ----
        cmdStr : string
          Formatted telegram string. We add the bus ID

        Returns
        -------
        raw : string
          The full, unmodified, response from the device. 
        """

        if isinstance(cmdStr, str):
            cmdStr = cmdStr.encode('latin-1')

        cmdStr = b'%%%d%s' % (self.busID, cmdStr)

        return cmdStr
