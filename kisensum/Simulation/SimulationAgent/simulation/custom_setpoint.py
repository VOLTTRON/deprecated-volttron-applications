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
    pass


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
    pass


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
    pass