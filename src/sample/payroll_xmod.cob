      ******************************************************************
      * PAYROLL_XMOD.COB  --  cross-module (whole-codebase) demo caller
      * for LAZARUS. Identical payroll math to payroll.cob, EXCEPT the
      * tax rate + bracket are NOT defined here: they come from the
      * shared copybook TAXRATES.CPY via COPY. The progressive-bracket
      * rule (rate switches above TC-BRACKET-LIMIT) is therefore split
      * ACROSS two files — recoverable only by reading the codebase as a
      * whole, which is exactly what migrate(cobol_paths=[...]) provides.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-XMOD.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY TAXRATES.
       01  WS-GROSS-PAY      PIC 9(7)V99 COMP-3.
       01  WS-TAX            PIC 9(7)V99 COMP-3.
       01  WS-NET            PIC 9(7)V99 COMP-3.
       01  WS-IN             PIC X(12).

       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-IN.
           MOVE FUNCTION NUMVAL(WS-IN) TO WS-GROSS-PAY.
           IF WS-GROSS-PAY > TC-BRACKET-LIMIT
               COMPUTE WS-TAX ROUNDED = WS-GROSS-PAY * TC-HIGH-RATE
           ELSE
               COMPUTE WS-TAX ROUNDED = WS-GROSS-PAY * TC-TAX-RATE
           END-IF.
           COMPUTE WS-NET = WS-GROSS-PAY - WS-TAX.
           DISPLAY WS-NET.
           STOP RUN.
