from datetime import datetime


def interval_start(ts, interval):
    """Takes a timestamp and interval length (in minutes) and returns a new timestamp indicating the interval start.
    Example:
        Inputs: ts = "2018-08-08 12:34:56.789" interval = 15
        Return: "2018-08-08 12:30:00.000"

    Helpful ts functions and properties. May use any of [year, month, day, hour, minute, second, microsecond]:
    ts.replace(year=2020, hour=15, microsecond=0) will return "2020-08-08 15:34:56.000"
    ts.minute will return 34
    ts.day will return 8

    :param ts: Datetime stamp
    :param interval: Interval length (in minutes)
    :return: Datetime stamp representing the start of the interval
    """
    aligned_minute = ts.minute - ts.minute % interval
    return ts.replace(minute=aligned_minute, second=0, microsecond=0)


def new_interval(ts1, ts2, interval):
    """Tests if two timestamps fall within the same interval

    :param ts1: Timestamp 1
    :param ts2: Timestamp 2
    :param interval: Interval length (in minutes)
    :return: True if the two timestamps fall in different intervals, False if they are in the same interval
    """
    return interval_start(ts1, interval) != interval_start(ts2, interval)


def calc_average_power(power_now, time_now, time_previous, avg_power_previous, interval_length):
    """Calculate the current average microgrid power for the given interval.

    Python help: when subtracting timestamps, you can use the total_seconds() method to return a float representation of
    the timedelta. Ex: (ts1-ts2).total_seconds()

    :param power_now: Current microgrid power reading
    :param time_now: Current simulation timestamp
    :param time_previous: Most recent previous power reading timestamp
    :param avg_power_previous: Running average of power readings for the interval
    :param interval_length: Length of interval (in minutes)

    :return: avg_power_now: newly calculated average interval power
    """

    # Check to see if we are in a new interval. If we are, set the current average power to the net power reading. If
    # we are not, update the average power based on how long it has been since the last reading.
    if new_interval(time_now, time_previous, interval_length):
        avg_power_now = power_now
    else:
        # Calculate how much time has elapsed for each interval and how much time has passed since the last update
        elapsed_time = (time_now - interval_start(time_now, interval_length)).total_seconds() or 1
        update_time = (time_now - time_previous).total_seconds()

        # Calculate average power
        avg_power_now = (avg_power_previous * (elapsed_time - update_time) + power_now * update_time) / elapsed_time
    return avg_power_now


def calc_setpoint(power_now, setpoint_previous, time_now, avg_power_now, interval_length, target_power,
                  max_charge_kw, max_discharge_kw):
    """Calculate a control setpoint that will keep the microgrid power as close to the target_power as possible. Keep
    in mind that a control_setpoint cannot dispatch greater than max_charge_kw, nor discharge less
    than negative (-)max_discharge_kw

    :param power_now: Current microgrid power reading
    :param setpoint_previous: The previous setpoint sent to the inverter/battery
    :param time_now: Current simulation timestamp
    :param avg_power_now: Current average power reading for the interval
    :param interval_length: Length of interval (in minutes)
    :param target_power: Control threshold for the microgrid
    :param max_charge_kw: Max allowable charge for the battery
    :param max_discharge_kw: Max allowable discharge for the battery
    :return: setpoint: Control setpoint to send to the inverter/battery
    """

    interval_length_seconds = interval_length * 60
    # Calculate how much time has elapsed and how much time is remaining for each interval
    elapsed_time = (time_now - interval_start(time_now, interval_length)).total_seconds()
    remaining_time = (interval_length_seconds-elapsed_time) or 1

    # Our new target is calculated based on how much time is remaining in the interval and the current avg power
    target = ((target_power * interval_length_seconds) - (avg_power_now * elapsed_time)) / remaining_time
    setpoint = target - power_now + setpoint_previous

    # Limit our setpoint based on the rated max charge and discharge of the battery
    if setpoint > max_charge_kw:
        setpoint = max_charge_kw
    if setpoint < 0 and abs(setpoint) > max_discharge_kw:
        setpoint = -max_discharge_kw
    return setpoint


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
    # Takes two datetimes and checks to see if they are in the same month
    def new_month(ts1, ts2):
        return ts1.month != ts2.month

    # Initialize target to default setting
    meter_target = sim_data.get('meter_target', reduced_meter_target)

    # If we are listening to Events, use default and reduced meter targets depending on if the event is currently in
    #  progress
    if sim_data.get('start_event', None):
        start_time = datetime.strptime(sim_data['start_event'], "%Y-%m-%d %H:%M:%S+00:00")
        end_time = datetime.strptime(sim_data['end_event'], "%Y-%m-%d %H:%M:%S+00:00")
        if start_time < time_now < end_time:
            meter_target = reduced_meter_target
        else:
            meter_target = default_meter_target
    # If we have not received Events, use reduced meter target for a low-ball initial target, and then check for new
    #  intervals. When intervals roll over, check the avg power, and if it sets a new peak, update the meter target.
    else:
        if new_month(time_previous, time_now):
            meter_target = reduced_meter_target
        elif new_interval(time_now, time_previous, interval_length):
            if avg_power_previous > meter_target:
                meter_target = avg_power_previous

    return meter_target
