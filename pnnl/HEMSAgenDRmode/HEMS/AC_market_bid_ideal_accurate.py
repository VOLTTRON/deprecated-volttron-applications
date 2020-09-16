import math
from scipy.optimize import fsolve

def calTmpONOFF(A_ETP, B_ETP, Dtemp, mdt):
    '''
    This function calculates tmpON tmpOFF from house properties 
    '''
    eAt = math.exp(A_ETP*mdt)
    temp = (eAt / A_ETP) * A_ETP * Dtemp + eAt / A_ETP * B_ETP - B_ETP / A_ETP
    
    return temp

def compute_time(A_ETP, B_ETP, T0, T1, mdt):
    '''
    Compute turnning on/off time taken
    '''
    
    data = (A_ETP, B_ETP, T0, T1)

    res = fsolve(func, 0.0, args=data)
    
    return res  

def func(x, *data):
    
    A_ETP, B_ETP, T0, T1 = data
    
    eAt = math.exp(A_ETP*x)
    
    func = eAt * T0 + (eAt - 1) / A_ETP * B_ETP - T1     
        
def AC_market_bid_ideal_accurate(controller, device_name, aggregator):
    
    # Inputs from market object:
    marketId = aggregator['market_id']
    clear_price = aggregator['clear_price']
    avgP = aggregator['average_price']
    stdP = aggregator['std_dev']
    bid_delay = controller['bid_delay']
            
    # Inputs from controller:
    houseName = controller[device_name]['houseName']
    ramp_low = controller[device_name]['ramp_low']
    ramp_high = controller[device_name]['ramp_high']
    range_low = controller[device_name]['range_low']
    range_high = controller[device_name]['range_high']
    deadband = controller[device_name]['deadband']
    last_setpoint = controller[device_name]['last_setpoint']
    minT = controller[device_name]['minT']
    maxT = controller[device_name]['maxT']
    direction = controller[device_name]['direction']
    
    # Inputs from house object:
    setpoint0 = controller[device_name]['setpoint0']
    demand = controller[device_name]['hvac_load']
    monitor = controller[device_name]['air_temperature']
    powerstate = controller[device_name]['power_state']
    
    # variables needed for double_price bid mode
    Ua = controller[device_name]['UA']
    Ca = controller[device_name]['air_heat_capacity']
    MassInternalGainFraction = controller[device_name]['MassInternalGainFraction']
    MassSolarGainFraction = controller[device_name]['MassSolarGainFraction']
    Qi = controller[device_name]['solar_gain']
    Qs = controller[device_name]['solar_gain']
    Qh = controller[device_name]['heat_cool_gain']
    Tout = controller[device_name]['outdoor_temperature']
    
    Dtemp = controller[device_name]['air_temperature']
    
    # Calculate A_ETP, B_ETP_ON, B_ETP_OFF
    A_ETP = -Ua / Ca
    B_ETP_ON = (Ua * Tout + 0.5 * Qi + 0.5 * Qs + Qh) / Ca
    B_ETP_OFF = (Ua * Tout + 0.5 * Qi + 0.5 * Qs) / Ca

#        print ("  sync:", demand, power_state, Dtemp, last_setpoint, deadband, direction, clear_price, avgP, stdP)

    deadband_shift = 0.5 * deadband
    
    # Controller update house setpoint if market clears  
    # Calculate bidding price - only put CN_DOUBLE_PRICE_ver2 here for HEMS agent
    if controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE_ver2':
        
        # Initialization of variables
        P_min = 0.0
        P_max = 0.0

        Q_max = 0.0
        Q_min = 0.0
        
        T_min = 0.0
        T_max = 0.0
        
        mdt = (controller['period']) / 3600.0
        
        # Calculate tmpON tmpOFF from house properties             
        tmpON = calTmpONOFF(A_ETP, B_ETP_ON, Dtemp, mdt)
        tmpOFF = calTmpONOFF(A_ETP, B_ETP_OFF, Dtemp, mdt)
        
        # Calculate bidding T_min, T_max, Q_min, Q_max                   
        if powerstate == 'OFF':

            if (Dtemp <= minT + deadband_shift) and (tmpOFF <= minT + deadband_shift):
                Q_max = 0
                T_min = minT
                Q_min = 0
                T_max = minT
            if (Dtemp < minT + deadband_shift) and (tmpOFF > minT + deadband_shift):
                tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, minT + deadband_shift, mdt)[0]
                Q_max = (mdt - tOFF) / mdt * demand
                T_min = minT
                Q_min = 0
                T_max = tmpOFF - deadband_shift
            if (Dtemp == minT + deadband_shift) and (tmpOFF > minT + deadband_shift):
                if tmpON >= minT - deadband_shift:
                    Q_max = demand
                else:
                    tON = compute_time(A_ETP, B_ETP_ON, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                T_min = minT
                Q_min = 0
                T_max = tmpOFF - deadband_shift
            if Dtemp > minT + deadband_shift:
                if tmpON >= minT - deadband_shift:
                    Q_max = demand
                    T_min = min(Dtemp - deadband_shift, tmpON + deadband_shift)
                else:
                    tON = compute_time(A_ETP, B_ETP_ON, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                    T_min = Dtemp - deadband_shift
                if tmpOFF <= maxT + deadband_shift:
                    Q_min = 0
                    T_max = max(Dtemp - deadband_shift, tmpOFF - deadband_shift)
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                    T_max = maxT
        
        if powerstate == 'ON':

            if (Dtemp >= maxT - deadband_shift) and (tmpON >= maxT - deadband_shift):
                Q_max = demand
                T_min = maxT
                Q_min = demand
                T_max = maxT
            if (Dtemp > maxT - deadband_shift) and (tmpON < maxT - deadband_shift):
                Q_max = demand
                T_min = tmpON + deadband_shift
                tON = compute_time(A_ETP, B_ETP_ON, Dtemp, maxT - deadband_shift, mdt)[0]
                Q_min = tON / mdt * demand
                T_max = maxT
            if (Dtemp == maxT - deadband_shift) and (tmpON < maxT - deadband_shift):
                Q_max = demand
                T_min = tmpON + deadband_shift                    
                if tmpOFF <= maxT + deadband_shift:
                    Q_min = 0
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                T_max = maxT
            if Dtemp < maxT - deadband_shift:
                if tmpOFF <= maxT + deadband_shift:
                    Q_min = 0
                    T_max = max(Dtemp + deadband_shift, tmpOFF - deadband_shift)
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                    T_max = Dtemp + deadband_shift
                if tmpON >= minT - deadband_shift:
                    Q_max = demand
                    T_max = min(Dtemp + deadband_shift, tmpON + deadband_shift)
                else:
                    tON = compute_time(A_ETP, B_ETP_ON, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                    T_min = minT
        
        if (Q_min == Q_max) and (Q_min == 0):
            P_min = 0.0
            P_max = 0.0
            bid_price = 0.0
        elif (Q_min == Q_max) and (Q_min > 0):
            P_min = P_cap
            P_max = P_cap
            bid_price = P_cap
            Q_min = 0.0
        else:
            bid_price = -1
            no_bid = 0

            # Bidding price when T_avg temperature is within the controller temp limit
            # Tmin
            P_min = -1
            if T_min > setpoint0:
                k_T = ramp_high
                T_lim = range_high
            elif T_min < setpoint0:
                k_T = ramp_low
                T_lim = range_low
            else:
                k_T = 0
                T_lim = 0
            
            bid_offset = 0.0001
            if P_min < 0 and T_min != setpoint0:
                P_min = avgP + (T_min - setpoint0)*(k_T * stdP) / abs(T_lim)   
            elif T_min == setpoint0:
                P_min = avgP
            
            if P_min < max(avgP - k_T * stdP, 0):
                P_min = 0
            if P_min > min(aggregator['price_cap'], avgP + k_T * stdP):
                P_min = aggregator['price_cap']
                
            # Tmax
            P_max = -1
            if T_max > setpoint0:
                k_T = ramp_high
                T_lim = range_high
            elif T_max < setpoint0:
                k_T = ramp_low
                T_lim = range_low
            else:
                k_T = 0
                T_lim = 0
            
            bid_offset = 0.0001
            if P_max < 0 and T_max != setpoint0:
                P_max = avgP + (T_max - setpoint0)*(k_T * stdP) / abs(T_lim)   
            elif T_max == setpoint0:
                P_max = avgP
            
            if P_max < max(avgP - k_T * stdP, 0):
                P_max = 0
            if P_max > min(aggregator['price_cap'], avgP + k_T * stdP):
                P_max = aggregator['price_cap']
            
            bid_price = (P_max + P_min) / 2.0
    
    return bid_price, P_max, P_min, Q_max, Q_min