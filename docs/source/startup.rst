XCU connections and start up sequence.
======================================

By default, the ``xcuActor`` runs on the ``BEE`` computer in the
cryostat pie pan. That computer is powered via the ``PCM`` controller,
which is generally controlled by the ``xcuActor``. As a bare minimum,
the ``PCM`` board and the ``BEE`` must be powered and on the network.

For the purposes of this document, I'll assume that the ``xcuActor``
will be run on the ``BEE`` itself. See XXXX if not. Also, I'll assume that
you are working on the ``r1`` camera. 


Power prerequisites
-----------------

The pie pan takes 24V and 48V power from the rack. The P3
connector provides the protected 24V, which powers all but the
motors, the cooler, the interlock board, and the turbo. 

Network connections
-------------------

The pie pan takes two Ethernet conections from the switch in the XXX
rack. P1 goes to the PCM from switch port 4, and P2 goes to the BEE
from switch port 3.

Hardware startup, part 0
------------------------

Starting for scratch (a powered-down rack), turn on the 48V switch,
turn the AUX Disconnect switch to On, and turn on the 24V switch. This
will provide power to the network switch in the rack and all parts of
the pie pan and cryostat. If the rack fan is not running, check the
48V and AUX supplies. 

From a machine with a direct network connection to the PFS network,
``ping bee-r1.pfs``. If the power, network and server are working, you
should get ping responses within 30s of powering up the 24V supply. If
not, open the back of the rack -- if the switch is not powered up
check the 24V supply. If the switch is powered up but does not have
link to the outside get link. If the switch has an outside link check
that the Ethernet cable labelled 'PCM' has link and is flashing. If
that is OK check on the server that the DHCP packets from the PCM are
being received and being given the right address. If that is the case
I bet you can ping it.

Software startup, part 0
------------------------

The hosts in the pie pan need to be assigned IP addresses from a
well-defined DHCP server which provides DNS names. See the XXX
document for details.

The ``tron`` hub must be running on a server which has access to the
PFS network.

The ``pfscore`` actor must be running and connected to ``tron``.

XCU actor startup
----------------

The core software depends on the PCM being powered and reachable. See
part 0.

Starting from scratch (a freshly booted PCM), here is the order:

 1. establish a command connection to ``tron``. 
 2. power up the BEE, with ``pfscore power cam=r1 port=bee on``
 3. wait about 45s for the bee to boot. It should automatically
    connect to ``tron``. You should also be able to ping it (``ping
    bee-r1.pfs``). If not, check the "BEE" Ethernet cable for link &
    traffic, and the DHCP server for proper traffic.
 4. Send ``pfscore inventory`` to get a listing of available
    devices. The "cams" keyword is based on the reacability of the PCM
    boards. In the case of this test I see ``cams=r1,o1``
    
    
