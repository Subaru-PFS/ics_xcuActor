#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('connect', '[<controllers>]', self.connect),
            ('monitor', '<controllers> <period>', self.monitor),
         ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("xcu_xcu", (1, 1),
                                        keys.Key("controllers", types.String()*(1,None),
                                                 help='the names of 1 or more controllers to load'),
                                        keys.Key("controller", types.String(),
                                                 help='the names a controller.'),
                                        keys.Key("period", types.Int(),
                                                 help='the period to sample at.'),
                                        )

    def monitor(self, cmd):
        period = cmd.cmd.keywords['period'].values[0]
        controllers = cmd.cmd.keywords['controllers'].values
        if 'coolor' not in self.actor.monitors:
            self.actor.monitors['cooler'] = 0
            
        for c in controllers:
            self.actor.monitor(c, period, cmd=cmd)
                
        cmd.finish()

    def controllerKey(self):
        controllerNames = self.actor.controllers.keys()
        key = 'controllers=%s' % (','.join([c for c in controllerNames]))

        return key
    
    def connect(self, cmd, doFinish=True):
        """ Reload all controller objects. """

        if 'controllers' in cmd.cmd.keywords:
            controllers = cmd.cmd.keywords['controllers'].values
        else:
            controllers = eval(self.actor.config.get(self.actor.name, 'controllers'))
        controllers = map(str, controllers)

        for dev in controllers:
            try:
                self.actor.attachController(dev)
            except Exception as e:
                cmd.fail('text="failed to connect controller %s: %s"' % (dev, e))
                return
        cmd.finish()
        

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        
        cmd.inform('text=%s' % (qstr("Present, with controllers=%s" % (self.actor.controllers.keys()))))
        cmd.finish()

