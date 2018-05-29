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
    that requires a special P8 connector on the back of the piepan
    which feeds a female USB for a keyboard. There is one at
    IDG.

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

    On a linux host, connect with something like ``miniterm.py --eol cr
    --raw socket://moxa-sp3:4001``. That would be for b3; adjust to
     taste. See step 0.
    
    The last step of the BIOS work rebooted the BEE: you should see
    booting stuff in the miniterm.py session. Again, hold down F4 from
    power up to break into the BIOS. Do that now, and note the MAC address 
    of the board for the DHCP/DNS server. 

    While there:
    - Advanced/Miscellaneous Config: Disable the second (CN30) Ethernet
    - Advanced/Serial Port Config: Set CN8 to 2 ports

    If you need/want to power-cycle the BEE, from the PFS server
    invoke ``pcm.py --cam=b3 --off=bee --on=bee``.
    
 2. reboot to install disk image.

    If still using the USB keyboard, restart while holding down F12
    (forces network/PXE boot).  If using the serial console, restart
    while holding down F3, then choose Network...00C8.
    
 3. install OS image. Reboot.

    Start the image server. On the IDG server (192.168.1.252 from
    inside the IDG network), log in and invoke `nc -v -q 5 -l -p 9000
    < /tftpboot/bee.hdd`. Leave that window open until you have
    installed the image.
    
    Power bee down.

    Connect to the serial console, hold down the F3 key. Wait a few
    seconds after the BIOS stuff starts scrolling. This should bring
    you to the boot device selection page. Chose the single network.

    The PXE boot should bring to a Debian installer menu. Chose
    Advanced Options, then Rescue Mode.

    Select the default (hit return) for the language and
    location. Check that the hostname is as expected ("bee-b1", say);
    accept pfs as the domain name.

    Default Debian mirror country and host, default (no) proxy.

    It will then build a runnable Linux system in RAM, which is all we
    need.
    
    If fetching time takes too long, just cancel out of that step.

    Default time zone.

    Now it gets more interesting. It should tell you that there are no
    disk partitions (a lie), or list the existing ones. If the former,
    Continue to rescue mode; if the latter, choose 'Do not
    use a root file syatem'.

    At the next menu Execute a shell, then confirm that choice.

    At the BusyBox '#' prompt, invoke "fdisk -l", which should find
    /dev/sda and some partitions. If not, stop.

    Invoke the download, writing directly to the bare hard drive: `nc
    tron.pfs 9000 > /dev/sda`. You should see confirmation in the
    server window. The transfer takes a while (3-4 minutes). Both the
    server and the BEE should return to their respective prompts.

    Reboot (ON THE BEE!!!): `reboot`. Stuff should scroll by,
    eventually ending with login prompt.
    
 4. At some point, tune the BIOS settingts a bit:

    - Advanced/Miscellaneous Config: Disable the second (CN30) Ethernet
    - Advanced/Serial Port Config: Set CN8 to 2 ports
