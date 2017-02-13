BEE BIOS Configuration
======================

Before a new BEE is commisioned, the BIOS must be configured and the
disk image loaded.

 0. Requirement: the per-spectrograph :doc:`MOXA must be configured
    <MOXA>` and the BEE's serial console line connected. The address
    will be ``moxa-spN.pfs`` for N in 1..4 (the spectrograph number),
    port 400X for X in 1..3 (the dewar number: Blue=1, Red=2,
    NIR=3). Since it is a network device you should not need to
    specify a baud rate, but it will be 38400 baud.

 1. enable the serial console. We try to do this without requiring a
    monitor, but you do need to connect a USB keyboard. As it stands
    that requires a standard motherboard-to-USB adapter.

    - On powerup, hold down the DEL key for ~15s
    - 3*Right (to Boot)
    - 7*Down RET (into Console Redirection)
    - RET Down RET (enable Console Redirection)
    - 2*Down RET (to speed selection)
    - 2*Down RET (38400 8,n,1)
    - ESC 4*Right RET RET (Save config and exit)
    
    **NOTE**: This sequence only works for BIOSes where the serial console
    has _not_ been configured.

    When booting using the serial console, F4 (and not DEL) brings you
    to the BIOS, and F3 (not F11) brings you to the boot device
    chooser.

 2. check serial console.

    On a linux host, connect with something like ``miniterm.py --cr
    socket://moxa-sp3:4001``. That would be for b3; adjust to taste.
    
    The last step of the BIOS work rebooted the BEE: you should see
    booting stuff in the miniterm.py session. Again, hold down F4 from
    power up to break into the BIOS. Do that now, and note the MAC address 
    of the board for the DHCP/DNS server. 

    If you need/want to power-cycle the BEE, from the PFS server
    invoke ``pcm.py --cam=b3 --off=bee --on=bee``.
    
 2. reboot to install disk image.

    If still using the USB keyboard, restart while holding down F12
    (forces network/PXE boot).  If using the serial console, restart
    while holding down F3, then choose Network...00C8.
    
 3. install OS image. Reboot.

 4. At some point, tune the BIOS settingts a bit:

    - Advanced/Miscellaneous Config: Disable the second (CN30) Ethernet
    - Advanced/Serial Port Config: Set CN8 to 2 ports
