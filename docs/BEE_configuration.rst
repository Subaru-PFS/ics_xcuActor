BIOS
----

From blank:

Advanced/CPU
------------

. speedstep off
. C-state on
. Enhanced C-states on

Advanced/SATA
-------------

. SATA Controller: AHCI


Advanced/Miscellaneous
----------------------

. GbE CN20: Enabled
. GbE CN20 LAN Boot: Enabled
. GbE CN30: disabled

Boot
----


. enable speedstep, confirm c-states enabled
. boot display to VGA only
. lower dynamic video to 128M
. enable PCI E Active State Power Mgmt
. Look more closely at the PCIe config
. 1x standard serial RS-232 ports on first port (COM1, for console)
. 2x standard serial RS-232 ports on first port (COM2/4)
. enable watchdog timer
. disable LCD
. disable PS/2 mouse
. enable GbE WOL
. console redirect (COM1,ITQ4)
. ACPI v3.0
. enable headless ACPI mode
. MPS 1.4

