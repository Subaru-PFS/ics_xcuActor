import logging

class CryoMode(object):
    """Track, as much as we need to, the states of the devices controlling
    the cryostat's basic operating mode: whether cooling, pumping,
    warming, etc.

    For now, a command sets the mode.

    """
    validModes = ('unknown', 'idle', 'pumpdown', 'cooldown', 'operation', 'warmup')
    
    def __init__(self, actor, logLevel=logging.INFO):
        self.actor = actor
        self.logger = logging.getLogger('cryomode')
        self.mode = 'unknown'

    def _cmd(self, cmd):
        if cmd is None:
            return self.actor.bcast
        else:
            return cmd

    def genKeys(self, cmd=None):
        cmd = self._cmd(cmd)
        cmd.inform(f'cryoMode={self.mode}')
        
    def setMode(self, newMode, cmd=None):
        if newMode not in self.validModes:
            raise ValueError(f"{newMode} is not a valid cryo mode")
        self.mode = newMode
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
