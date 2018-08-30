PFS Cryostat pumping.
=====================

Document ID: PFS-SPS-PRU020100-01_Pumping_Control.rst
Document link: https://github.com/Subaru-PFS/ics_xcuActor/blob/master/docs/PFS-SPS-PRU020100_Pumping_Control.rst

Each of the twelve PFS cryostats has its own gatevalve and turbo
pump. The entire instrument is backed by two roughing lines, each with
one pump and one pressure gauge, and each plumbed to a fixed set of
six cryostats.

All of the pumps, gatevalves, and gauges are under software
control. This document gives an overview of the hardware, then
describes the software design and the basic operating procedures.

Hardware control
----------------

Pumping control for a given cryostat involves two actors and five
pieces of hardware. The cryostat's `ics_xcuActor` controls the
gatevalve and the turbo pump, and reads the internal cryostat
pressure. One of two `ics_roughActor` s controls a roughing pump and
reads a pressure gauge.

Both the turbo and the roughing pump are controlled over serial
lines. The roughing pump can be manually turned on or off, the turbo
cannot.

The gatevalve (Agilent (VAT) Series 12)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The gatevalve is pneumatically driven, and controlled by 5V open and
close signals from the interlock board. If air is lost, the valve does
not close by itself, but will stay closed if it is closed.

Gatevalve interlock
^^^^^^^^^^^^^^^^^^^

One of the few hardware interlocks on the instrument is a per-cryostat
gatevalve interlock, which requires both a physical jumper and power
to an interlock circuit board before the open signal will be passed to
the gatevalve.

If power to the interlock board is lost or turned off, the gatevalve
will close.

If power to the BEE is lost or the BEE is rebooted, the gatevalve will
close.

The turbo pump (Edwards EXT75DX)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ics_xcuActor` simply starts or stops the pump, and reads
status. There is a lower-speed "standby" mode; the commands to enter
that are implemented but we do not expect to use it.

An "at full-speed" signal is used to close the gatevalve when the
pump speed drops below 50-80% (TBD) of full speed. This is essentially
a direct wire: it is not dependent on any computing hardware or
software.

We do enable electro-mechanical braking on the turbopump.

The roughing pump (Edwards nXDS15i)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ics_roughActor` simply starts or stops the pump, and reads
status. There is a lower-speed "standby" mode; we might switch to that
once the roughing lines have been pulled down to a decent backing
vacuum.

The actor tracks and broadcasts the estimated times until tip-seal and
bearing maintenance, and declares a warning when those expire or the
controller raises an alert.

Pressure gauges (Pfeiffer M200)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As of 2018-09, all pressure gauges are full-range models, with both a
Pirani and a cold-cathode gauge. Readings near 1e-3 mbar and near
atmosphere are not very precise.

Software control
----------------

The most important piece of controllable hardware is the gatevalve. We
put most of our safety logic into being careful about when to allow
opening and when to force closing the valve.

There are two distinct situations to handle: when the cryostat is
under vacuum and when it is not.

In order to open the gatevalve the pressure difference across the
valve is supposed to be -- per the manual -- no greater than 30 mbar.

Opening the gatevalve with the cryostat at/near atmosphere (>= 1 mbar)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both the cryostat(s) and the roughing line line must be back-filled to
atmosphere. [ See the manual procedures for that.... ]

At atmosphere, we will not always be able to determine pressures well
enough for the differential pressure check to pass. So we will
often/usually require human judgement and action.

In order for the `gatevalve open` command to actually open the valve,

 - the interlock board must be powered up (`xcu_b1 power on
   interlock`)
 - the interlock jumper must be installed on Jxxx at the bottom of the
   piepan
 - all pumps must be *off*.
 - the pressures *should* be within 30 mbar of each other.

The 'gatevalve open' command accepts an optional `ok` argument, which
overrides the 30 mbar pressure check. [ It also accepts a
`reallyforce` argument, which overrides all checks. DO NOT SEND
THIS unless you are at sea level and have spoken with the Site
Engineer in person. ]

Procedures are important here. WE DO NOT KNOW WHAT THE PHYSICAL
EFFECTS OF DRIVING THE VALVE THROUGH A PRESSURE OFFSET ARE.

Opening the gatevalve with the cryostat under vacuum (< 1 mbar)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the cryostat is at vacuum, the checks enforced before a `gatevalve
open` command is applied are:

- the interlock board must be powered up (`xcu_b1 power on
  interlock`)
- the interlock jumper must be installed on Jxxx at the bottom of the
  piepan
- both the roughing and turbo pumps must be *on*.
- the pressures must be within 30 mbar of each other.

There are are few further bits of logic. Basically, when the gatevalve
is open, the `xcuActor` actively watches for anomalies in the
pressures, interlock, and roughing pump. Specifically:

- if an open command fails, the open signal is deasserted.
- if the measured state of the gatevalve or interlock changes, the
  valve is commanded closed.
- while a roughing pump is on, it broadcasts the pressure and pump
  status continuously (0.2 - 1 HZ). If that data stops or the
  pressure rises or the pump shows an error, the gatevalve is closed.

Note that the hardware signal from the turbo pump which closes the
gatevalve when the pump speed falls below 50-80% (TBD) should handle
turbo problems, so we do not watch for those. And the check for
gatevalve changes will ensure that that gatevalve stays closed if the
turbo spins down.

We are *not* (yet) watching site air pressure. The gatevalve does
*not* close on pressure loss, so we probably should.

  **JEG**: *Julien: we need a pressure switch on the standby tank*

Pumping scenarios
-----------------

The two sections above cover the gatevalve logic for a single
cryostat. With six cryostats on a single roughing line, we just need
to make sure that any pumping actions conform to those two scenarios.

a. Pump one or more cryostats which are all at atmosphere.

   1. *Confirm* that all cryostats **and** the roughing line are actually
      at atmosphere: backfill per the procedures as
      necessary. **DANGER**: only backfill cryostats which are *known*
      not to be cold.

      [ How do we determine that the cryostat has been backfilled? Are
      we adding check valves? CPL ]

        **JEG**: *this is a procedural question. We have the gauges,
        which we can calibrate, but NOT to 30 mB. We still do not have
        a completely safe way to backfill, but can almost certainly
        come up with one. I will think about it. Since a popoff on a
        backfill line does not have to deal with/seal against high
        vacuum, and since 30 mbar on a 4-inch disk generates about 5
        pounds of force, it does not seem unreasonable to make a
        popoff which does relieve at a few millbar on the backfill
        line. Not completely trivial, but easy. Balloons work, too.*

      [ How do we backfill roughing line? With what? CPL ]

        **JEG**: *need hardware AND procedure*

   2. Open the gatevalves on all cryostats to pump.
   3. Turn on roughing pump
   4. Once roughing line gets down to ~1 mbar, turn on turbos on all
      cryostats to pump.
   5. [Not yet decided] turn the rougher to standby ???

b. Pump one or more cryostats which are all at vacuum.

   1. Turn on roughing pump
   2. Once roughing line gets down to ~1 mbar, turn on turbos on all
      cryostats to pump.
   3. Once roughing line pressure stabilizes and all turbos are at
      full speed, open the appropriate gatevalves.

c. Some cryostats are pumping, want to pump more from atmosphere.

   1. close gatevalve on pumping cryostats
   2. turn off turbos, turn off roughing pump.
   3. Goto procedure a1 for the new cryostats
   4. Once Goto procedure b2. once the new cryostats get to ~1 mbar.

d. Some cryostats are pumping, want to pump more from vacuum.

   1. Goto procedure b2.
