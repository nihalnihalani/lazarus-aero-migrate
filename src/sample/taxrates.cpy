      ******************************************************************
      * TAXRATES.CPY  --  shared copybook for the LAZARUS cross-module
      * (whole-codebase) demo. The tax rate + bracket threshold live
      * ONLY here; any program that COPYs this file inherits them. This
      * is the cross-module business rule the agent must recover: the
      * constant is defined in the .cpy and used by N programs, so the
      * rule SPANS files (it is invisible if you read the caller alone).
      ******************************************************************
       01  TAX-CONSTANTS.
           05  TC-TAX-RATE        PIC V999    VALUE 0.225.
           05  TC-BRACKET-LIMIT   PIC 9(7)V99 VALUE 5000.00.
           05  TC-HIGH-RATE       PIC V999    VALUE 0.310.
