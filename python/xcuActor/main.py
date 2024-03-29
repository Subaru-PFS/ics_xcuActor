#!/usr/bin/env python

import argparse
import logging
from twisted.internet import reactor

import actorcore.ICC
from ics.utils.sps import spectroIds
import cryoMode

class OurActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, site=None,
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
                                   idDict=self.ids.idDict)

        self.logger.setLevel(logLevel)

        self.everConnected = False

        self.monitors = dict()
        self.statusLoopCB = self.statusLoop

    def isNir(self):
        """ Return True if we are a NIR cryostat. """

        return self.ids.arm == 'n'

    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.actorConfig),
                                         self.actorConfig.keys()))

    def connectionMade(self):
        if self.everConnected is False:
            _needModels = [self.name]
            self.logger.info(f'adding models: {_needModels}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {self.models.keys()}')

            self.cryoMode = cryoMode.CryoMode(self)

            logging.info("Attaching all controllers...")
            self.allControllers = self.actorConfig['controllers']['starting']
            self.attachAllControllers()
            self.everConnected = True

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
                        logLevel=args.logLevel)
    theActor.run()

if __name__ == '__main__':
    main()
