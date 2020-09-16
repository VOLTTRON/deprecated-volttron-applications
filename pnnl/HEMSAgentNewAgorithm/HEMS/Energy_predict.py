import numpy as np

from scipy.linalg import expm

from ACTemp_control import ACTemp_control
from WHTemp_control import WHTemp_control

def Energy_predict(setpoint1, setpoint2): 

    # input from HEMS: Tmin Tmax, Tdesired, halfband, power, COP, T_out, Q_s,
    # T_inlet T_amb Dtemp(1,1)
    # model parameters: AC and WH
    
    # Initialize simulation time step and duration;
    
    tf = 24 # simulation time = 24hr;
    ddt = 1.0/3600.0*30 # device simulation step = 0.5min;
    Dtimestamps = (tf-ddt) / ddt + 1
    # Dtimestamps = 0:ddt:tf-ddt
    Dtimes = int(Dtimestamps)
    # Dtimes = length(Dtimestamps)
    mdt = 1.0/3600.0*300.0 # market simulation step = 5min;
    Mtimes = Dtimes/(mdt/ddt)
    
    # Initialize device parameters and weather data;
    
    # AC parameters
    T_out = 90*np.ones((1,Dtimes)) # temperature prediction
    Q_s = np.zeros((1,Dtimes))
    
    U_A = 716.483587456827
    C_a = 1188.59330141685
    
    power_1 = 4e3 # unit: W
    COP_1 = 10
    A_ETP_1 = -U_A/C_a
    B_ETP_ON_1 = (U_A*T_out+Q_s-COP_1*power_1)/C_a
    B_ETP_OFF_1 = (U_A*T_out+Q_s)/C_a
    T_set_1_original = setpoint1 # 70 - changed to subscribe to real device setpoint
    T_set_1_control = T_set_1_original
    halfband_1 = 2
    
    Dtemp_1_original = np.zeros((1,Dtimes))
    Dstatus_1_original = np.zeros((1,Dtimes))
    factor_1_original = np.zeros((1,Dtimes))
    P_1_original = np.zeros((1,Dtimes))
    Dtemp_1_original[0,0] = T_set_1_original
    Dstatus_1_original[0,0] = 0
    
    Dtemp_1_control = np.zeros((1,Dtimes))
    Dstatus_1_control = np.zeros((1,Dtimes))
    factor_1_control = np.zeros((1,Dtimes))
    P_1_control = np.zeros((1,Dtimes))
    Dtemp_1_control[0,0] = Dtemp_1_original[0,0]
    Dstatus_1_control[0,0] = 0
    
    # WH parameters
    
    power_3 = 4e3; # unit: W
    
    C_p = 1
    C_w = 417.11
    Q_elec = power_3/0.29
    T_amb = 70*np.ones((1,Dtimes))
    T_inlet = 60*np.ones((1,Dtimes))
    UA_wh = 3.02689849161905
    
    mdot = np.zeros((1,Dtimes))
    A_ETP_3 = -(mdot*C_p+UA_wh)/C_w
    B_ETP_ON_3 = (mdot*C_p*T_inlet+UA_wh*T_amb+Q_elec)/C_w
    B_ETP_OFF_3 = (mdot*C_p*T_inlet+UA_wh*T_amb)/C_w
    T_set_3_original = setpoint2 # 130 - changed to subscribe to real device setpoint
    T_set_3_control = T_set_3_original
    halfband_3 = 2
    
    Dtemp_3_original = np.zeros((1,Dtimes))
    Dstatus_3_original = np.zeros((1,Dtimes))
    factor_3_original = np.zeros((1,Dtimes))
    P_3_original = np.zeros((1,Dtimes))
    Dtemp_3_original[0,0] = T_set_3_original
    Dstatus_3_original[0,0] = 0
    
    Dtemp_3_control = np.zeros((1,Dtimes))
    Dstatus_3_control = np.zeros((1,Dtimes))
    factor_3_control = np.zeros((1,Dtimes))
    P_3_control = np.zeros((1,Dtimes))
    Dtemp_3_control[0,0] = Dtemp_3_original[0,0]
    Dstatus_3_control[0,0] = 0
    
    
    # individual simulation
    
    hr_start = 16
    hr_stop = 21
    
    # AC simulation
    Tmin_1 = 66
    Tmax_1 = 78
    # E_1_reduction_temp = 0:0.5:(Tmax_1-T_set_1_original)
    E_1_reduction_temp = np.arange(0,(Tmax_1-T_set_1_original+0.5),0.5)
    E_1_reduction_day = np.zeros(np.size(E_1_reduction_temp))
    E_1_reduction_period = np.zeros(np.size(E_1_reduction_temp))
    
    # uncontrolled
    P_1_original[0,0] = power_1*Dstatus_1_original[0,0]
    for k in range(0,Dtimes-1):
        Dtemp_1_original[0,k+1],Dstatus_1_original[0,k+1],factor_1_original[0,k] = ACTemp_control(Dtemp_1_original[0,k],A_ETP_1,B_ETP_ON_1[0,k],B_ETP_OFF_1[0,k],halfband_1,T_set_1_original,Dstatus_1_original[0,k],ddt);
        P_1_original[0,k] = P_1_original[0,k]+power_1*factor_1_original[0,k]
        P_1_original[0,k+1] = power_1*Dstatus_1_original[0,k+1]
    E_1_original = np.cumsum(P_1_original)*ddt*3600/3.6e6 # Ws to kWh;
    
    # controlled
    for i in range(0,np.size(E_1_reduction_temp, axis=0)):
        P_1_control[0,0] = power_1*Dstatus_1_control[0,0]
        for k in range(0,Dtimes-1):
            if k>=hr_start*1/ddt and k<=hr_stop*1/ddt-1:
                T_set_1_control = T_set_1_original+E_1_reduction_temp[i]
            else:
                if (k) % (1.0/3.0/ddt) == 0:
                    T_set_1_control = T_set_1_control + E_1_reduction_temp[i]/(23+1.0/3.0-hr_stop)/3.0
                    if T_set_1_control > T_set_1_original:
                        T_set_1_control = T_set_1_original
            Dtemp_1_control[0,k+1],Dstatus_1_control[0,k+1],factor_1_control[0,k] = ACTemp_control(Dtemp_1_control[0,k],A_ETP_1,B_ETP_ON_1[0,k],B_ETP_OFF_1[0,k],halfband_1,T_set_1_control,Dstatus_1_control[0,k],ddt);
            P_1_control[0,k] = P_1_control[0,k]+power_1*factor_1_control[0,k]
            P_1_control[0,k+1] = power_1*Dstatus_1_control[0,k+1]
    
        E_1_control = np.cumsum(P_1_control)*ddt*3600.0/3.6e6
        
        temp = np.cumsum(E_1_original)-np.cumsum(E_1_control)
        E_1_reduction_day[i] = temp[-1]/(float(24-hr_start)/ddt)  # "temp[-1]" replaces "temp(end)", i.e., get last element of temp
    
    # WH simulation
    Tmin_3 = 120
    Tmax_3 = 140
    E_3_reduction_temp = np.arange(0,(T_set_3_original-Tmin_3+0.5),0.5)
    E_3_reduction_day = np.zeros(np.size(E_3_reduction_temp))
    E_3_reduction_period = np.zeros(np.size(E_3_reduction_temp))
    
    # uncontrolled
    P_3_original[0,0] = power_3*Dstatus_3_original[0,0]
    for k in range(0,Dtimes - 1):
        Dtemp_3_original[0,k+1],Dstatus_3_original[0,k+1],factor_3_original[0,k] = WHTemp_control(Dtemp_3_original[0,k],A_ETP_3[0,k],B_ETP_ON_3[0,k],B_ETP_OFF_3[0,k],halfband_3,T_set_3_original,Dstatus_3_original[0,k],ddt);
        P_3_original[0,k] = P_3_original[0,k]+power_3*factor_3_original[0,k]
        P_3_original[0,k+1] = power_3*Dstatus_3_original[0,k+1]
    E_3_original = np.cumsum(P_3_original)*ddt*3600.0/3.6e6; # Ws to kWh
    
    # controlled
    for i in range(1,np.size(E_3_reduction_temp, axis=0)):
        P_3_control[0,0] = power_3*Dstatus_3_control[0,0]
        for k in range(0,Dtimes-1):
            if k>=hr_start*1/ddt and k<=hr_stop*1/ddt-1:
                T_set_3_control = T_set_3_original-E_3_reduction_temp[i]
            else:
                if (k) % (1.0/3.0/ddt) == 0:
                    T_set_3_control = T_set_3_control + E_3_reduction_temp[i]/(23+1.0/3.0-hr_stop)/3.0
                    if T_set_3_control > T_set_3_original:
                        T_set_3_control = T_set_3_original
            Dtemp_3_control[0,k+1],Dstatus_3_control[0,k+1],factor_3_control[0,k] = WHTemp_control(Dtemp_3_control[0,k],A_ETP_3[0,k],B_ETP_ON_3[0,k],B_ETP_OFF_3[0,k],halfband_3,T_set_3_control,Dstatus_3_control[0,k],ddt);
            P_3_control[0,k] = P_3_control[0,k]+power_3*factor_3_control[0,k]
            P_3_control[0,k+1] = power_3*Dstatus_3_control[0,k+1]
        
        E_3_control = np.cumsum(P_3_control)*ddt*3600/3.6e6
        
        temp = np.cumsum(E_3_original)-np.cumsum(E_3_control)
        E_3_reduction_day[i] = temp[-1]/(float(24.0-hr_start)/ddt)  # "temp[-1]" replaces "temp(end)", i.e., get last element of temp
    
    
    print 'E_1_reduction_temp: ', E_1_reduction_temp
    print 'E_1_reduction_day: ', E_1_reduction_day
    
    print 'E_3_reduction_temp: ', E_3_reduction_temp
    print 'E_3_reduction_day: ', E_3_reduction_day

    return E_1_reduction_temp, E_1_reduction_day, E_3_reduction_temp, E_3_reduction_day

