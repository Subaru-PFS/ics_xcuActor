XCU connections and start up sequence.
======================================

By default, the ``xcuActor`` runs on the ``BEE`` computer in the
cryostat pie pan. That computer is powered via the ``PCM`` controller,
which is generally controlled by the ``xcuActor``. As a bare minimum,
the ``PCM`` board and the ``BEE`` must be powered and on the network.

For the purposes of this document, I'll assume that the ``xcuActor``
will be run on the ``BEE``. See XXXX if not. Also, I'll assume that
you are working on the ``r1`` camera.


Power connections
-----------------

The pie pan takes 24V and 48V power from the XXX rack. The P3
connector provides the protected 24V, which powers all but the
motors, the cooler, the interlock board, and the turbo. 

Network connections
-------------------

The pie pan takes two Ethernet conections from the switch in the XXX
rack. P1 goes to the PCM from switch port 4, and P2 goes to the BEE
from switch port 3.

The hosts in the pie pan need to be assigned IP addresses from a
well-defined DHCP 

Software startup
----------------

Starting from scratch (a powered-down pie pan), here is the order:

 1. log on to a computer which has the ``ics_xcuActor`` product and
    which can reach the given pie pan's network. Setup ics_xcuActor.
 2. power up the pie pan's 24V feed. If you want, now or later, check
    that the rack switch's router shows link and traffic on port 4.
 3. wait for a few seconds for the PCM to get an IP address. Or ping
    it with ``ping pcm-r1``.
 4. power the BEE up with "``pcm.py --camera=r1 --on bee``"
 5. wait about 90s for the bee to boot. You can also ping it (``bee-r1``).
 6. ssh to the BEE, as user ``pfs``: ``ssh pfs@bee-r1`
 7. 
