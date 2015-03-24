#!/usr/bin/env python

import logging

import actorcore.ICC

class OurActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, debugLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name, 
                                   productName=productName, 
                                   configFile=configFile)


def main():
    theActor = OurActor('xcu', productName='xcuActor')
    theActor.run()

if __name__ == '__main__':
    main()
