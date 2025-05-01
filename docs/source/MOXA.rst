MOXA Configuration
==================

The IA5000A-series NPort MOXAs come from the factory with a static
address: 192.168.127.254. DHCP is disabled.  I cannot bring myself to
comment, but all new MOXAs need to be reconfigured to be useful..

The simplest scheme is probably to connect a laptop to one of the MOXA
Ethernet ports. For the rack MOXAs where you cannot see the MOXA box,
connect to either one of the Ethernet ports on the 48V box. Set
the laptop adddress to 192.168.127.1, boot the MOXA, then connect to
the web page at ``http://192.168.127.254/``.

Old MOXAs have no password set, but new ones require one. The only
username is ``admin`` and the default password is ``moxa``. If you
need to use or set one, please use the general-purpose PFS password.

At the top front page, note the MAC address. If you need to, register
the MAC address with the DHCP server now so that when the MOXA is
rebooted it gets the correct IP address.

In the panel on the left, go to Network Settings and change the IP
configuration pulldown to DHCP. Click Submit at the bottom of the
page.

Hit Save/Restart and (quickly) plug the MOXA into the normal
Ethernet. It should appear at the DHCP-given address in a few
seconds. To continue with configuration, connect to the web server at
the new address.

One other change applies to all ports on all MOXAs: they must be set
to listen for incoming raw TCP connections. Open the left panel's
Operating Settings and select Port 1. Set the Operation mode to TCP
Server. Also confirm that it only allows one connection and that the
Local TCP Port is 400x, x={1..4}. And apply the change to all ports.

PFS per-spectrograph configuration
----------------------------------

The per-spectrograph rack MOXAs serve the three BEE serial consoles on
ports 2-4, and the ion pump controllers on Port 1.

1. Open the left panel's Serial Settings, then choose Port 2. Set it to
38400,8,1,None,None,RS-232, and select ports P2, P3, P4. Submit but
do not then Save/Restart.

2. In the left panel's Serial Settings, choose Port 1. Set it to
38400,8,1,None,None, RS-485 2-wire. Submit.

3. Then in the Operating Settings Port 1 page, set Delimiter 1 to 03
and enable it. And set the Delimiter process to Delimiter+2. Submit
and Restart. [The ionpump controller replies all end with ``0x03``
followed by a two-byte CRC. If the MOXA can recognize this it can
manage bus contention better.]

PFS roughing pump configuration
-------------------------------

The single MOXA for the roughing pumps serves roughing pumps on two
ports and ion gauges on the other two.

Besides setting the Operation mode on all ports to ``TCP Server``, the only change is to the Serial Settings:

- Ports P1 and P2 should be set to 9600,8,1,None,None,RS-232
- Ports P3 and P4 should be set to 9600,8,1,None,None,RS-485 2-wire.
   [ Flow Control is currently listed as RTS/CTS on P3 and P4. I think
   this makes no sense for RS-485 and is a MOXA bug. ]


