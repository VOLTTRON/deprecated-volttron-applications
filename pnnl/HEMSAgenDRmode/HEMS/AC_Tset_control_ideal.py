import datetime
import logging

def AC_Tset_control_ideal(config, controller, device_name, aggregator, controller_bid):
    
    # Inputs from market object:
    marketId = aggregator['market_id']
    clear_price = aggregator['clear_price']
    avgP = aggregator['average_price']
    stdP = aggregator['std_dev']
    bid_delay = controller['bid_delay']
    
    # Inputs from controller:
    setpoint0 = controller[device_name]['setpoint0']
    ramp_low = controller[device_name]['ramp_low']
    ramp_high = controller[device_name]['ramp_high']
    range_low = controller[device_name]['range_low']
    range_high = controller[device_name]['range_high']
    deadband = controller[device_name]['deadband']
    last_setpoint = controller[device_name]['last_setpoint']
    minT = controller[device_name]['minT']
    maxT = controller[device_name]['maxT']
    
    # # Update controller last market id and bid id
    controller_bid[device_name]['rebid'] = 0 
            
    # Calculate updated set_temp
    if clear_price < avgP and range_low != 0:
        set_temp = setpoint0 + (clear_price - avgP) * abs(range_low) / (ramp_low * stdP)
    elif clear_price > avgP and range_high != 0:
        set_temp = setpoint0 + (clear_price - avgP) * abs(range_high) / (ramp_high * stdP)
    else:
        set_temp = setpoint0 #setpoint0
    
    # Check if set_temp is out of limit
    if set_temp > maxT:
        set_temp = maxT
    elif set_temp < minT:
        set_temp = minT
    
    # Update last_setpoint if changed
    if last_setpoint != set_temp:
        last_setpoint = set_temp
    
    return last_setpoint
                    