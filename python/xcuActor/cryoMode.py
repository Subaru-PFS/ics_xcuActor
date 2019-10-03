import logging
from functools import partial
from threading import Timer

import fysom


class CryoMode(object):
    """Track, as much as we need to, the states of the devices controlling
    the cryostat's basic operating mode: whether cooling, pumping,
    warming, etc.

    For now, a command sets the mode.

    """
    validModes = ('unknown', 'offline', 'standby', 'pumpdown', 'cooldown', 'operation', 'warmup', 'bakeout')
    standbyTime = dict(toPumpdown=600,
                       toCooldown=600)

    def __init__(self, actor, logLevel=logging.INFO):
        self.actor = actor
        self.logger = logging.getLogger('cryomode')
        callbacks = dict([(f'on{mode}', self.modeChangeCB) for mode in self.validModes])

        events = [{'name': 'toOffline', 'src': ['unknown', 'pumpdown', 'cooldown', 'operation', 'warmup', 'bakeout', 'standby'], 'dst': 'offline'},
                  {'name': 'toPumpdown', 'src': ['offline'], 'dst': 'pumpdown'},
                  {'name': 'toBakeout', 'src': ['offline', 'pumpdown'], 'dst': 'bakeout'},
                  {'name': 'toCooldown', 'src': ['offline', 'pumpdown'], 'dst': 'cooldown'},
                  {'name': 'toOperation', 'src': ['offline', 'cooldown'], 'dst': 'operation'},
                  {'name': 'toWarmup', 'src': ['cooldown', 'operation'], 'dst': 'warmup'}]

        for name, delay in self.standbyTime.items():
            goEvent = f'go{name}'
            callbacks[f'on{name}'] = partial(self.standby, delay, goEvent)

            [delayedEvent] = [event for event in events if event['name'] == name]
            events.append(dict(name=goEvent, src='standby', dst=delayedEvent['dst']))
            delayedEvent['dst'] = 'standby'

        self.mode = fysom.Fysom({'initial': 'unknown',
                                 'events': events,
                                 'callbacks': callbacks
                                 })

    def standby(self, delay, funcname, e):
        t = Timer(delay, self.triggerMode, args=(funcname,))
        t.start()

    def triggerMode(self, event):
        trigger = getattr(self.mode, event)

        if 'goto' in event and self.mode.current != 'standby':
            self.actor.bcast.inform(f'cryoMode no longer in standby mode')
            return

        return trigger()

    def _cmd(self, cmd):
        if cmd is None:
            return self.actor.bcast
        else:
            return cmd

    def modeChangeCB(self, e):
        self.actor.bcast.inform(f'cryoMode={e.dst}')

    def genKeys(self, cmd=None):
        cmd = self._cmd(cmd)
        cmd.inform(f'cryoMode={self.mode.current}')

    status = genKeys

    def setMode(self, newMode, cmd=None):
        if newMode not in self.validModes:
            raise ValueError(f"{newMode} is not a valid cryo mode")

        self.triggerMode(event=f'to{newMode.capitalize()}')
        self.genKeys(cmd)

    def updateCooler(self, cmd=None):
        pass

    def updateGatevalve(self, cmd=None):
        pass

    def updateTurbo(self, cmd=None):
        pass

    def updateIonpump(self, cmd=None):
        pass

    def updateHeater(self, cmd=None):
        pass
