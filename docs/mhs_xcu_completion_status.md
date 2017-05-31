# Completion status, 2017-05-30[^1]

[^1]: In ics_xcuActor/docs/status.md

## XCU actor subsystems

------------------------------------------------------------------------------
System        Completed Risk Notes
------------- --------- ---- -------------------------------------------------
cryocooler    85%       Low  Handle two coolers

gatevalve     90%       Low  Complete failure tests

ionpump       95%       Low

motors        95%       Low  Minor tickets.

power         95%       Low

roughpump     90%       Low  Pull out into roughingActor\
                             Add lifetime checks

temperatures  90%       Low

heaters       80%       Low  Needs emergency shutdown loop

turbo         95%       Low  Drop serial repeater (INSTRM-xxx)
------------------------------------------------------------------------------


## CCD actor subsystems

------------------------------------------------------------------------------
System       Completed  Risk  Notes
------------ ---------  ----  ------------------------------------------------
FEE          90%        Low   Pull config into `ics_config`

FPGA/CCD     90%        Low   Pull config into `ics_config`
------------------------------------------------------------------------------

## HX actor subsystems

------------------------------------------------------------------------------
System       Completed  Risk  Notes
------------ ---------  ----  ------------------------------------------------
HX readout   80%        Med   Interleaving is the unknown
------------------------------------------------------------------------------

## All ICS

------------------------------------------------------------------------------
System         Completed Risk Notes
-------------- --------- ---- ------------------------------------------------
Alerts         10%       Low  

Configuration  10%       Low  `Use ics_config`

Keywords       40%       Low  
------------------------------------------------------------------------------

