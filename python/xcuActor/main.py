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

        self.monitors = dict(turbo=0,
                             ionpump=0,
                             gauge=0,
                             temps=0,
                             ltemps=0,
                             cooler=0,)
        
        self.statusLoopCB = self.statusLoop
        
    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            # self.attachAllControllers()
            self.everConnected = True

            # reactor.callLater(10, self.status_check)

    def statusLoop(self, controller):
        try:
            self.callCommand("%s status" % (controller))
        except:
            pass
        
        if self.monitors[controller] > 0:
            reactor.callLater(self.monitors[controller],
                              self.statusLoopCB,
                              controller)
            
    def monitor(self, controller, period, cmd=None):
        if controller not in self.monitors:
            raise RuntimeError('text="%s is not a known controller"' % (controller))

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:
            cmd.warn('text="starting loop %s for %s via %s"' % (self.monitors[controller],
                                                                controller, self.statusLoopCB))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="NOT starting loop %s for %s via %s"' % (self.monitors[controller],
                                                                    controller, self.statusLoopCB))
            
def main():
    theActor = OurActor('xcu', productName='xcuActor')
    theActor.run()

if __name__ == '__main__':
    main()
