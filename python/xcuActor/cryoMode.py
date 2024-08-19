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
    validModes = ('unknown', 'offline', 'standby', 'roughing', 'pumpdown', 'ionpumping', 'cooldown', 'operation', 'warmup', 'bakeout')
    standbyTime = dict(toPumpdown=600,  # turbo pump takes about 2 minutes to reach 90000RPM
                       toCooldown=600,  # cryoCooler power takes about 4 minutes to go over 70W lower limit
                       toIonpumping=30)  # Gives you half a minute to close the gatevalve.

    def __init__(self, actor, logLevel=logging.INFO):
        self.actor = actor
        self.logger = logging.getLogger('cryomode')
        self.delayedEvent = None

        callbacks = dict([(f'on{mode}', self.modeChangeCB) for mode in self.validModes])

        events = [{'name': 'toOffline',
                   'src': ['unknown', 'standby', 'roughing', 'pumpdown', 'ionpumping', 'cooldown', 'operation', 'warmup', 'bakeout'],
                   'dst': 'offline'},
                  {'name': 'toRoughing', 'src': ['offline'], 'dst': 'roughing'},
                  {'name': 'toPumpdown', 'src': ['offline', 'roughing', 'ionpumping', 'bakeout'], 'dst': 'pumpdown'},
                  {'name': 'toBakeout', 'src': ['offline', 'roughing', 'pumpdown'], 'dst': 'bakeout'},
                  {'name': 'toIonpumping', 'src': ['offline', 'pumpdown'], 'dst': 'ionpumping'},
                  {'name': 'toCooldown', 'src': ['offline', 'pumpdown', 'ionpumping'], 'dst': 'cooldown'},
                  {'name': 'toOperation', 'src': ['offline', 'cooldown'], 'dst': 'operation'},
                  {'name': 'toWarmup', 'src': ['offline', 'cooldown', 'operation'], 'dst': 'warmup'}]

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
        self.reload()
        self.actor.models[self.actor.name].keyVarDict['turboSpeed'].addCallback(self.turboAtSpeed)

    @property
    def instData(self):
        return self.actor.actorData

    def reload(self):
        """ reload persisted state, so it can survive shutdown."""
        try:
            persisted, = self.instData.loadKey('cryoMode')
        except:
            persisted = 'offline'

        # go to offline first to respect transition.
        self.mode.toOffline()
        # no need to go further.
        if persisted in ['offline']:
            return
        # go to event
        event = getattr(self.mode, f'to{persisted.capitalize()}')
        # call event
        event()

    def turboAtSpeed(self, keyvar):
        """ turbo at speed callback. """
        # dont need to go even further.
        if self.delayedEvent is None or not self.delayedEvent.is_alive():
            return

        (event,) = self.delayedEvent.args

        # if not in transient pumpdown state or transition already passed.
        if event != 'gotoPumpdown' or self.mode.current == 'pumpdown':
            return

        try:
            atSpeed = keyvar.getValue() >= 90000
        except ValueError:
            return

        if atSpeed:
            # go to pumpdown mode righ away.
            self.mode.gotoPumpdown()

    def standby(self, delay, funcname, e):
        if self.delayedEvent is not None:
            self.delayedEvent.cancel()

        self.delayedEvent = Timer(delay, self.triggerMode, args=(funcname,))
        self.delayedEvent.daemon = True
        self.delayedEvent.start()

    def triggerMode(self, event):
        trigger = getattr(self.mode, event)

        if 'goto' in event and self.mode.current != 'standby':
            self.actor.bcast.inform(f'state machine not triggered : cryoMode no longer in standby')
            return

        return trigger()

    def _cmd(self, cmd):
        if cmd is None:
            return self.actor.bcast
        else:
            return cmd

    def modeChangeCB(self, e):
        self.actor.bcast.inform(f'cryoMode={e.dst}')
        # not persisting transient and initial state.
        if e.dst in ['unknown', 'standby']:
            return
        # persist cryoMode
        self.instData.persistKey('cryoMode', e.dst)

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
