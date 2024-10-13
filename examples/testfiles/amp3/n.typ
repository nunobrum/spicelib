.MODEL NMOS NMOS(         LEVEL   = 8
+VERSION = 3.2            TNOM    = 27             TOX     = 7.4E-9
+XJ      = 2.3E-7         NCH     = 2E17           VTH0    = 0.5910286
+K1      = 0.5665015      K2      = -2.01788E-5    K3      = 43.254121
+K3B     = -8.3666578     W0      = 5.7493E-6      NLX     = 1.72968E-7
+DVT0W   = 0.018702       DVT1W   = 5.3E6          DVT2W   = -0.032
+DVT0    = 3.6629308      DVT1    = 0.5219583      DVT2    = -0.05
+VBM     = -3.3           U0      = 528.8985       UA      = 1.476303E-9
+UB      = 2.083775E-19   UC      = 5.368193E-11   VSAT    = 9.011E4
+A0      = 0.8775883      AGS     = 0.214565       B0      = 4.40815E-8
+B1      = 1E-7           KETA    = 0.0166414      A1      = 0
+A2      = 1              RDSW    = 816.0400837    PRWG    = 9.336953E-4 
+PRWB    = 0.0539535      WR      = 1              WINT    = 4.572104E-8
+LINT    = 3.15E-8        XL      = 0              XW      = 0
+DWG     = -2.687564E-9   DWB     = 4.696235E-9    VOFF    = -0.1406745
+NFACTOR = 1.4442501      CIT     = 0              CDSC    = 1E-3
+CDSCD   = 0              CDSCB   = 0              ETA0    = 0
+ETAB    = -0.0722136     DSUB    = 0.56           PCLM    = 0.8351951
+PDIBLC1 = 0.2896433      PDIBLC2 = 2.920887E-3    PDIBLCB = 0
+DROUT   = 0.7796106      PSCBE1  = 6.510097E8     PSCBE2  = 2.948305E-5
+PVAG    = 0.0587596      DELTA   = 1.618913E-3    ALPHA0  = 2.2E-7
+BETA0   = 18.45          ALPHA1  = 0.78           RSH     = 2.7
+JS      = 1.6E-7         JSW     = 4.0E-13
+MOBMOD  = 1              PRT     = 0              UTE     = -1.7395947
+KT1     = -0.1635661     KT1L    = -1.173597E-8   KT2     = 0.022
+UA1     = 1.081907E-10   UB1     = -8.22235E-19   UC1     = -1E-10
+AT      = 3.3E4          NQSMOD  = 0              ELM     = 5 
+WL      = 9.246632E-22   WLN     = 1              WW      = 0
+WWN     = 1              WWL     = -1.28698E-20   LL      = 0
+LLN     = 1              LW      = 0              LWN     = 1
+LWL     = 0              AF      = 1              KF      = 3.9167E-28
+NOIMOD  = 1              EF      = 1              CAPMOD  = 3
+XPART   = 0              CGDO    = 1.04294E-10    CGSO    = 1.04294E-10
+CJ      = 8.86E-4        PB      = 0.904          MJ      = 0.369 
+CJSW    = 2.65E-10       PBSW    = 0.894          MJSW    = 0.356 
+CJSWG   = 2.84E-10       PBSWG   = 0.896          MJSWG   = 0.356
+CKAPPA  = 0.6 		  CLC     = 1E-8           CLE     = 0.6
+NOFF    = 1              ACDE    = 1
+MOIN    = 15             TPB     = 0              TPBSW   = 0
+TPBSWG  = 0              TCJ     = 0              TCJSW   = 0
+TCJSWG  = 0
* definition of selectors for ELDO
*for junction leakage
*+DIOLEV=7	TLEVI=3		
+XTI=3	N=1.09
* junction capacitance, AD AP, AS and PS calculation
* +ALEV=3		DCAPLEV=0
+HDIF=0.4875E-6
* external seris resistance
*+RLEV=4
+)