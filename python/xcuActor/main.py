#!/usr/bin/env python

import actorcore.Actor

class OurActor(actorcore.Actor.Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.Actor.Actor.__init__(self, name, 
                                       productName=productName, 
                                       configFile=configFile)

        self.configureDevices()

    def configureDevices(self):
        self.devices = dict()

#
# To work
def main():
    theActor = OurActor('xcu', productName='ics_xcuActor')
    theActor.run()

if __name__ == '__main__':
    main()
