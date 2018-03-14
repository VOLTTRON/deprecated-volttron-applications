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
    

def WH_market_bid_ideal_accurate(controller, device_name, aggregator):
    
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
    powerstate = controller[device_name]['power_state']
    
    # variables needed for double_price bid mode
    mdot = controller[device_name]['mdot']
    Ua = controller[device_name]['UA']
    Cp = controller[device_name]['Cp']
    Cw = controller[device_name]['Cw']
    Q_elec = controller[device_name]['Q_elec']
    T_amb = controller[device_name]['T_amb']
    T_inlet = controller[device_name]['T_inlet']
    Tout = controller[device_name]['outdoor_temperature']
    
    Dtemp = controller[device_name]['water_flow_temperature']

    # Calculate A_ETP, B_ETP_ON, B_ETP_OFF
#     mdot = mdot * 1.5 # not sure if needed
    A_ETP = -(mdot * Cp + Ua) / Cw
    B_ETP_ON = (mdot * Cp * T_inlet + Ua * T_amb + Q_elec) / Cw
    B_ETP_OFF = (mdot * Cp * T_inlet + Ua * T_amb) / Cw

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
            
            if (Dtemp >= maxT - deadband_shift) and (tmpOFF >= maxT - deadband_shift):
                Q_max = 0
                T_min = maxT
                Q_min = 0
                T_max = maxT
            if (Dtemp > maxT - deadband_shift) and (tmpOFF < maxT - deadband_shift):
                tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, maxT - deadband_shift, mdt)[0]
                Q_max = (mdt - tOFF) / mdt * demand
                T_max = maxT
                Q_min = 0.0
                T_min = tmpOFF + deadband_shift
            if (Dtemp == maxT - deadband_shift) and (tmpOFF < maxT - deadband_shift):                   
                if tmpON <= maxT + deadband_shift:
                    Q_max = demand
                else:
                    tOFF = compute_time(A_ETP, B_ETP_ON, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                T_max = maxT
                Q_min = 0
                T_min = tmpOFF + deadband_shift
            if Dtemp < maxT - deadband_shift:
                if tmpON <= maxT + deadband_shift:
                    Q_max = demand
                    T_max = max(Dtemp + deadband_shift, tmpON - deadband_shift)
                else:
                    tON = compute_time(A_ETP, B_ETP_ON, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                    T_max = Dtemp + deadband_shift
                if tmpOFF >= minT - deadband_shift:
                    Q_min = 0
                    T_min = min(Dtemp + deadband_shift, tmpOFF + deadband_shift)
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                    T_min = minT

        if powerstate == 'ON':

            if (Dtemp <= minT + deadband_shift) and (tmpON <= minT + deadband_shift):
                Q_max = demand
                T_min = maxT
                Q_min = demand
                T_max = maxT
            if (Dtemp < minT + deadband_shift) and (tmpON > minT + deadband_shift):
                Q_max = demand
                T_max = tmpON - deadband_shift
                tON = compute_time(A_ETP, B_ETP_ON, Dtemp, minT + deadband_shift, mdt)[0]
                Q_min = tON / mdt * demand
                T_min = minT
            if (Dtemp == minT + deadband_shift) and (tmpON > minT + deadband_shift):
                Q_max = demand
                T_max = tmpON - deadband_shift
                if tmpOFF >= minT - deadband_shift:
                    Q_max = 0
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                T_min = minT
            if Dtemp > minT + deadband_shift:
                if tmpOFF >= minT - deadband_shift:
                    Q_min = 0
                    T_min = min(Dtemp - deadband_shift, tmpOFF + deadband_shift)
                else:
                    tOFF = compute_time(A_ETP, B_ETP_OFF, Dtemp, minT - deadband_shift, mdt)[0]
                    Q_min = (mdt - tOFF) / mdt * demand
                    T_min = Dtemp - deadband_shift
                if tmpON <= maxT + deadband_shift:
                    Q_max = demand
                    T_max = max(Dtemp - deadband_shift, tmpON - deadband_shift)
                else:
                    tON = compute_time(A_ETP, B_ETP_ON, Dtemp, maxT + deadband_shift, mdt)[0]
                    Q_max = tON / mdt * demand
                    T_max = maxT
        
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

        # Bidding price when Dtemp temperature is within the controller temp limit
        # Tmin
        P_max = -1
        if T_min <= setpoint0:
            P_max = avgP + (T_min - setpoint0) * ramp_low * stdP / abs(range_low)
        
            if P_max < max(avgP - ramp_low * stdP, 0):
                P_max = 0
            if P_max > min(aggregator['price_cap'], avgP + ramp_low * stdP):
                P_max = aggregator['price_cap']
        
        if T_min > setpoint0:
            P_max = avgP + (T_min - setpoint0) * ramp_high * stdP / abs(range_high)
        
            if P_max < max(avgP - ramp_high * stdP, 0):
                P_max = 0
            if P_max > min(aggregator['price_cap'], avgP + ramp_high * stdP):
                P_max = aggregator['price_cap']
        
        
        # Tmax
        P_min = -1
        if T_max <= setpoint0:
            P_min = avgP + (T_max - setpoint0) * ramp_low * stdP / abs(range_low)
            
            if P_min < max(avgP - ramp_low * stdP, 0):
                P_min = 0
            if P_min > min(aggregator['price_cap'], avgP + ramp_low * stdP):
                P_min = aggregator['price_cap']
        
        if T_max > setpoint0:
            P_min = avgP + (T_max - setpoint0) * ramp_high * stdP / abs(range_high)
            
            if P_min < max(avgP - ramp_high * stdP, 0):
                P_min = 0
            if P_min > min(aggregator['price_cap'], avgP + ramp_high * stdP):
                P_min = aggregator['price_cap']
        
        bid_price = (P_max + P_min) / 2.0
    
    return bid_price, P_max, P_min, Q_max, Q_min