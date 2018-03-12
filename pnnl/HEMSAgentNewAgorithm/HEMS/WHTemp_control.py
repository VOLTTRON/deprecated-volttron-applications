import numpy as np
import math

def WHTemp_control(Dtemp_current,A_etp,B_etp_on,B_etp_off,halfband,T_set,Dstatus_current,ddt):

    eAt = math.exp(A_etp*ddt)

    factor = 0
    
    if Dstatus_current == 1:

        Dtemp_next = eAt*Dtemp_current + (eAt - 1) / A_etp * B_etp_on
        Dstatus_next = Dstatus_current
        # find index of Ta compoments outside range

        if Dtemp_next >= T_set+halfband: # need to turn off, since temperature over the deadband
            Dtemp_next = Dtemp_current
            sub_ddt = 1.0/3600.0
            repeatN = int((ddt-sub_ddt)/sub_ddt)
            for t in range(0, repeatN + 1):
#             for t in np.arange(sub_ddt,ddt,sub_ddt):
            # Python range function is equivalent, however "initial:step:stop" is reordered to (initial, stop, step)
            # for t = sub_ddt:sub_ddt:ddt
                if Dstatus_next == 1:
                    factor = factor+sub_ddt/ddt
                    Dtemp_next = Dtemp_next + (A_etp*Dtemp_next+B_etp_on)*sub_ddt
                    if Dtemp_next >= T_set+halfband:
                        Dstatus_next = 0
                else:
                    Dtemp_next = Dtemp_next + (A_etp*Dtemp_next+B_etp_off)*sub_ddt
#                   if Dtemp_next(1,1) >= T_set+halfband
#                       Dstatus_next = 1;
#                   end
            factor = factor-1
    else:
        # See above comments on scalar, np.linalg.lstsq, np.linalg.solve, and np.divide
        Dtemp_next = eAt*Dtemp_current + ((eAt-1)/A_etp)*B_etp_off
        Dstatus_next = Dstatus_current
        # find index of Ta compoments outside range

        if Dtemp_next <= T_set-halfband: # need to turn on, since temperature over the deadband
            Dtemp_next = Dtemp_current
            sub_ddt = 1.0 / 3600.0
            repeatN = int((ddt-sub_ddt)/sub_ddt)
            for t in range(0, repeatN + 1):
#             for t in np.arange(sub_ddt,ddt,sub_ddt):
            # for t = sub_ddt:sub_ddt:ddt
                if Dstatus_next == 0:
                    Dtemp_next = Dtemp_next + (A_etp*Dtemp_next+B_etp_off)*sub_ddt
                    if Dtemp_next <= T_set-halfband:
                        Dstatus_next = 1
                else:
                    factor = factor+sub_ddt/ddt
                    Dtemp_next = Dtemp_next + (A_etp*Dtemp_next+B_etp_on)*sub_ddt
#                   if Dtemp_next(1,1) <= T_set-halfband
#                       Dstatus_next = 0;
#                   end
    
    return Dtemp_next,Dstatus_next,factor
