XCU Devices
-----------

The ``xcuActor`` controls all the non-readout devices at the dewar pie pan. Specifically:

 - the PCM, which controls power to many other devices and provides
   communication to a few.

 - the BEE, which has the serial port to the turbo pump and the DIO
   connection to the gate valve and its interlock board.

 - the IDG temperature monitoring and heater board.

 - the cryocooler(s).

 - the ion pumps.

 - the motors, via the PCM board.

 - the ion gauge, via the PCM board.

 - the gatevalve, via onboard DIO pins and a kernel module.

By default the program runs on the ``BEE``, but can run anywhere
unless you want to control the turbo or the gate valve.


 
