PFS Cryostat pumping.
=====================

Document ID: PFS-SPS-PRU020100-03

Latest revision link: PFS-SPS-PRU020100_

Each of the twelve PFS cryostats has its own gatevalve and turbo
pump. The entire instrument is backed by two roughing lines, each with
one pump and one pressure gauge, and each plumbed to a fixed set of
six cryostats.

All of the pumps, gatevalves, and gauges are under software
control. This document gives an overview of the hardware, then
describes the software design and the basic operating procedures.

Hardware control
----------------

Pumping control for a given cryostat involves two actors and one
safety interlock. The cryostat's `ics_xcuActor` controls the gatevalve
and the turbo pump, and negotiates with the interlock controller to
read pressures just inside the gatevalve and just outside the turbo,
and to open the gatevalve. One of two `ics_roughActor` s controls a
roughing pump and reads a pressure gauge which is between the roughing
pump and any turbo pump.

The actual gatevalve control is done by the per-cryostat interlock
board, which always applies safety logic based on the turbo speed,
relative cryostat and roughing line pressures, and a hardware
interlock jumper.

Both the turbo and the roughing pump are controlled over serial
lines. The roughing pump can be manually turned on or off, the turbo
cannot.

The gatevalve (Agilent (VAT) Series 12)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The gatevalve is pneumatically driven, and controlled by 5V open and
close signals from the interlock board. If air is lost, the valve does
*not* close by itself, but will stay closed if it is closed.

Gatevalve interlock
^^^^^^^^^^^^^^^^^^^

The are two version of the interlock board, and all old ones are being
replaced in 2019-06. This document covers the _new_ board only.

One of the few hardware interlocks on the instrument is a per-cryostat
gatevalve interlock, which requires both a physical jumper and power
to an interlock circuit board before the open signal will be passed to
the gatevalve. The interlock board also has two directly connected
pressure sensors, one on the cryostat side of the gatevalve and one on
the roughing side of the turbo pump. These provide very good absolute
readings at or near atmosphere. The board uses those two pressures,
the turbo at-speed signal, and the physical jumper to control whether to
actually open the gatevalve, or whether to close the gatevalve while
it is open. The close-on-error logic runs autonomously on the
interlock board.

The board takes a digital request to open from the BEE, and provides
logic and pressure status over a serial line directly connected to the
BEE.

The interlock board blocks gatevalve opening:
 - if the interlock jumper is out or if the PCM-controlled power to the interlock is off.
 - if the pressure difference between the two sensors exceeds 30 mbar (settable threshold)
 - if the turbo is not at speed when either pressure is above 500 mbar (settable threshold)
 - if the gatevalve has been closed by any error. I.e. the gatevalve is *latched* closed.
   
The interlock board *closes* the gatevalve:
 - if power to the interlock board is lost or turned off. Pulling the jumper will do this.
 - if the open request signal from the BEE is lost. This happens when the BEE is rebooted/power-cycled.
 - if the turbo at-speed signal drops out after it has been asserted.
 - if the roughing line pressure rises to 1 mbar (settable threshold).
 - if the gatevalve open signal is not asserted within 3s of requesting an open (settable limit)


The turbo pump (Edwards EXT75DX)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ics_xcuActor` simply starts or stops the pump, and reads
status. There is a lower-speed "standby" mode; the commands to enter
that are implemented but we do not expect to use it.

An "at full-speed" signal is used to close the gatevalve when the
pump speed drops below 98% (settable) of full speed. This is essentially
a direct wire: it is not dependent on any computing hardware or
software.

We do enable electro-mechanical braking on the turbopump, but it is
still pretty slow to spin down.

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
Pirani and a cold-cathode gauge. Readings near 1e-3 mbar and above 10
mbar. The interlock pressure sensors are quite good at atmosphere, and
good enough down to 1 mbar. And we generally do not turn ionpumps on
above 10^-5 Torr.

Software control
----------------

The most important piece of controllable hardware is the gatevalve. We
put most of our safety logic into being careful about when to allow
opening and when to force closing the valve.

There are two distinct situations to handle: when the cryostat is
under vacuum and when it is not. In order to clearly disambiguate the
two, the `gatevalve open` command must actually be either `gatevalve
open atAtmosphere` or `gatevalve open underVacuum`.

In order to open the gatevalve the pressure difference across the
valve is supposed to be -- per the manual -- no greater than 30 mbar.

Opening the gatevalve with the cryostat at/near atmosphere (>= 1 Torr)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both the cryostat(s) and the roughing line line must be back-filled to
atmosphere. [ See the manual procedures for that.... ]

At atmosphere, we will not always be able to determine pressures well
enough for the differential pressure check to pass. So we will
often require human judgement and action.

In order for the `gatevalve open atAtmosphere` command to actually
open the valve,

- the interlock board must be powered up (`xcu_b1 power on
  interlock`)
- the interlock jumper must be installed on Jxxx at the bottom of the
  piepan
- both the roughing and the turbo pumps must be *off*.
- the pressures *should* be within 30 mbar of each other.

The 'gatevalve open' command accepts an optional `ok` argument, which
overrides the 30 mbar pressure check.

Procedures are important here. WE DO NOT KNOW WHAT THE PHYSICAL
EFFECTS OF DRIVING THE VALVE THROUGH A PRESSURE OFFSET ARE.

Opening the gatevalve with the cryostat under vacuum (< 1 mbar)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the cryostat is at vacuum, the checks enforced before a `gatevalve
open underVacuum` command is applied are:

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

1. Pump one or more cryostats which are all at atmosphere.

   a. *Confirm* that all cryostats **and** the roughing line are actually
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

   b. Open the gatevalves on all cryostats to pump.
   c. Turn on roughing pump
   d. Once roughing line gets down to ~1 mbar, turn on turbos on all
      cryostats to pump.
   e. [Not yet decided] turn the rougher to standby ???

2. Pump one or more cryostats which are all at vacuum.

   a. Turn on roughing pump
   b. Once roughing line gets down to ~1 mbar, turn on turbos on all
      cryostats to pump.
   c. Once roughing line pressure stabilizes and all turbos are at
      full speed, open the appropriate gatevalves.
   d. [Not yet decided] turn the rougher to standby ???

3. Some cryostats are pumping, want to pump more from atmosphere.

   a. close gatevalve on pumping cryostats
   b. turn off turbos, turn off roughing pump.
   c. Goto procedure 1a for the new cryostats
   d. Once the new cryostats get to ~1 mbar, goto procedure 2b. 

4. Some cryostats are pumping, want to pump more from vacuum.

   a. Goto procedure 2b.

Additional Notes
----------------

The `gatevalve open` command also accepts a `reallyforce` argument,
which overrides all checks. DO NOT SEND THIS unless you are at sea
level and have spoken with the Site Engineer in person. ] Now that the
interlock board itself applies safety logic, that `reallyforce` does
not actually work, but we will leave it in so that the request signal
can always be passed down if needed.


Interlock provisioning and updating
-----------------------------------

The interlock board has a PIC which needs firmware. If new, the
bootloader code needs to be installed, during which a serial number
will be assigned. The bootloader can currently only be installed by
Steve Hope at JHU.

Once the bootloader is installed, the real firmware can be installed
or updated using the `xcuActor`. The example command, for the `b2`
cryostat, is `oneCmd.py --level=d xcu_b2 interlock sendImage
path=/home/pfs/interlock_20190603_02.hex doReboot`. If no firmware has
ever been installed, do not use use `doReboot`.

Interlock testing
-----------------

The gatevalve requires ~70 psi on its air line.  Gatevalve operation
also requires the ability to backfill both the cryostat (with dry
nitrogen) and the roughing line.

For initial testing, both the cryostat and roughing line be at
atmosphere and that the roughing and turbo pumps be off but available.

The `xcuActor` `gatevalve status` command returns all available
gatevalve and interlock status. Specifically in the following
keywords:
- `gatevalve=0x34,closed,closed` The first word is the requested
  state, or "blocked" or "timedout". The last is the actual state of
  the gatevalve limit switches ("open", "closed", "unknown",
  "invalid").
  
- `interlockpressures=1.006e+03,1.004e+03`. Inside the cryostat and
  inside the roughing line. Should be v. good > 300 mbar, and good
  enough for engineering diagnostics down to 1 mbar. In operations we
  trust nothing between 0 and 300 mbar: either they are under decent
  vacuum or not.
  
- `interlock=0b110100,"pressure_equal, vacuum_ok, gv_closed"` The
  bitmask of the actual input and logic bits, and a text description
  of each set bit. Pay attention to that last one.
  

1. With the interlock jumper _in_, `gatevalve status` should show
   believable atmospheric pressures (in mbar), and the two sensors
   should be very close (<1 mbar). If not, re-check that both sides
   have been vented. If after that they still differ, find and fix the
   physical problem.
2. With the interlock jumper _out_, `gatevalve status` should show
   9999.99 for both sensors.
3. Put the interlock jumper back in. Make sure that the interlock
   circuit is powered (`power on interlock`)
4. Try to open the gatevalve incorrectly: `gatevalve open
   underVacuum`. This should fail, with complaints about the turbo and
   roughing pumps being off and for the dewar and roughing pressures
   being too high. These messages are mostly from the xcuActor, and
   the interlock board is not asked to open the valve.  Note that if
   you bypassed the xcu logic with `gatevalve open underVacuum` it
   would open: there is nothing unsafe about the current
   configuration.
5. Test the differential pressure lockout. Turn the roughing pump on
   for a second or two: we only need to get past a differential
   pressure of 30 mbar. `gatevalve status` should show the second
   pressure below the first.
6. Try to open the gatevalve: `gatevalve open atAtmosphere`. This
   should fail, with complaints about pressures.
7. Repeat, but bypssing the xcu logic: `gatevalve open atAtmosphere
   reallyforce`. This should also be rejected, but by the interlock
   board, The `gatevalve` keyword should show that the interlock
   request was blocked.
8. The new interlock board _latches_ the gatevalve closed after an
   error. Explicitly request a close (`gatevalve close`) to clear the
   latched error.

9. Vent the roughing line to atmosphere. `gatevalve status` should
   show nearly equal pressures.
10. Finally, open the gatevalve: `gatevalve open atAtmosphere`. The
    `gatevalve` keyword and the `interlockStatus` keyword should show
    the gatevalve request and position.
11. Turn on the roughing pump. Watch the two interlock gauges and the
    cryostat gauge as it pumps down to 10 torr. At the lower end the
    values should be within a factor of 1.5 or so.
12. Turn on the turbo. Let the turbo come up to speed (90000 rpm); the
    interlock "turbo" flag should come on. Let the cryostat pressure
    get down to 1e-4.
13. Turn off the turbo. At 88200 rpm the gatevalve should close (and
    the "turbo" flag from the interlock should turn off).
14. Turn the turbo back on. Once it comes up to speed try opening the
    gatevalve. Again, that should _fail_ due to the latched close
    signal. Send an explicit `gatevalve close` and open again.
15. Corfirm that dropping PCM power closes the gatevalve: `power off
    interlock`. The valve should close just as for the turbo spindown
    test. Turn the power back on and confirm that the closure is
    latched. If you want, clear the latched state with a `close` and
    re-open.

If you need to backfill the cryostat you should use the interlock
pressure sensors.

.. _PFS-SPS-PRU020100: https://github.com/Subaru-PFS/ics_xcuActor/blob/master/docs/PFS-SPS-PRU020100_Pumping_Control.rst
