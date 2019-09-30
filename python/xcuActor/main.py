#!/usr/bin/env python

import argparse
import logging
from twisted.internet import reactor

import actorcore.ICC
from pfscore import spectroIds
import cryoMode

class OurActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, site=None,
                 logLevel=logging.INFO):
        if name is not None:
            cam = name.split('_')[-1]
        else:
            cam = None

        self.ids = spectroIds.SpectroIds(cam, site)

        if name is None:
            name = 'xcu_%s' % (self.ids.camName)
            
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName, 
                                   configFile=configFile)

        self.logger.setLevel(logLevel)

        
        self.everConnected = False

        self.monitors = dict()
        self.statusLoopCB = self.statusLoop

        self.roughMonitor = None
        self.cryoMode = cryoMode.CryoMode(self)
        
    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True

            if self.name[-1] in '12':
                self.roughName = 'rough1'
            else:
                self.roughName = 'rough2'

            try:
                roughOverride = self.config.get(self.name, 'roughActor')
                if roughOverride is not None:
                    self.roughName = roughOverride
            except:
                pass

            _needModels = [self.name, self.roughName]
            self.logger.info(f'adding models: {_needModels}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {self.models.keys()}')
            
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
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:
            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller],
                                                          controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))
            
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default=None, type=str, nargs='?',
                        help='identity')
    parser.add_argument('--cam', default=None, type=str, nargs='?',
                        help='ccd name, e.g. r1')
    args = parser.parse_args()

    if args.name is not None and args.cam is not None:
        raise RuntimeError('only one of --cam and --name can be specified')
    if args.cam is not None:
        args.name = f'xcu_{args.cam}'
        
    theActor = OurActor(args.name,
                        productName='xcuActor',
                        configFile=args.config,
                        logLevel=args.logLevel)
    theActor.run()

if __name__ == '__main__':
    main()
