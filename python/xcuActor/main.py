#!/usr/bin/env python

import logging
from twisted.internet import reactor

import actorcore.ICC

class OurActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, debugLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name, 
                                   productName=productName, 
                                   configFile=configFile)

        self.everConnected = False
        
    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            # self.attachAllControllers()
            self.everConnection = True

            reactor.callLater(10, self.status_check)

    def status_check(self):
        """ Perform the periodic total status report of the system. """
        self.callCommand("pressure")
        reactor.callLater(self.config.getint('gauge','repeatEvery'),
                          self.status_check)


def main():
    theActor = OurActor('xcu', productName='xcuActor')
    theActor.run()

if __name__ == '__main__':
    main()
