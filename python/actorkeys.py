KeysDictionary("xcu", (1, 1),
               Key("pressure", Float(invalid="NaN", units="Torr"),
                   help="Ion gauge pressure."),
               Key("temps", Float(invalid="NaN", units="K")*4,
                   help="Lakeshore temperatures"),
               Key("coolerTemps", Float(invalid="NaN", units="K")*3,
                   help="Cryocooler temperatures. Setpoint, Reject, Tip."),
               )


               
