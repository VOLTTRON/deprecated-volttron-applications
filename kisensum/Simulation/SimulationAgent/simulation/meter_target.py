def calc_target_power(sim_data, time_now, time_previous, avg_power_previous, default_meter_target, reduced_meter_target,
                      interval_length):
    """For the initial timeframe, the target will be a default value of 470. If we are controlling using VTN Events,
    we need to check if we are in an event and reduce the meter_target if we are.

    :param sim_data: Dictionary of in memory information stored by the simulation agent
    :param time_now: Current simulation time
    :param time_previous: Most recent previous power reading timestamp
    :param avg_power_previous: Previous Avg Power calculation (needed as proxy for previous interval power when interval
        rolls over
    :param default_meter_target: Meter target when not under DR
    :param reduced_meter_target: Meter target when under DR event
    :param interval_length
    :return: Target setpoint for the meter
    """
    from datetime import datetime
    if sim_data.get('start_event', None):
        event_start_time = datetime.strptime(sim_data['start_event'], "%Y-%m-%d %H:%M:%S+00:00")
        event_end_time = datetime.strptime(sim_data['end_event'], "%Y-%m-%d %H:%M:%S+00:00")
    return default_meter_target
