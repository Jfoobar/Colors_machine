import utime

# Start date for your data, as a utime tuple
START_DATE_TUPLE = (2025, 1, 1, 0, 0, 0, 0, 0)
SECONDS_IN_DAY = 86400

def get_day_number(start_date_tuple):
    """Calculates the number of days since the start_date."""
    start_seconds = utime.mktime(start_date_tuple)
    today_seconds = utime.time()
    seconds_in_day = 86400
    return (today_seconds - start_seconds) // seconds_in_day

def get_sunset_minutes(day_number):
    """Retrieves sunset time (minutes past midnight) from CSV."""
    try:
        with open('sunset_data.csv', 'r') as csvfile:
            next(csvfile)  # Skip header
            for line in csvfile:
                parts = line.strip().split(',')
                if len(parts) == 2 and int(parts[0]) == day_number:
                    return int(parts[1])
        return None
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None

def get_sunset_time_tuple(utc_offset_s):
    """
    Calculates and returns the sunset time for today as a utime tuple,
    adjusted for a given UTC offset.
    Returns None if sunset data cannot be found.
    """
    # Get the current time as a utime tuple
    today_tuple = utime.localtime(utime.time() + utc_offset_s)
    
    # Convert tuples to seconds to calculate day difference
    start_seconds = utime.mktime(START_DATE_TUPLE)
    today_seconds = utime.time()
    
    # Calculate the day number from the difference in seconds
    day_num_to_get = (today_seconds - start_seconds) // SECONDS_IN_DAY

    sunset_minutes = get_sunset_minutes(day_num_to_get)

    if sunset_minutes is not None:
        # Get today's time tuple
        year, month, day, _, _, _, _, _ = today_tuple
        
        # Calculate the sunset hour and minute from the total minutes
        sunset_hour = sunset_minutes // 60
        sunset_minute = sunset_minutes % 60
        
        # Return a time tuple for sunset
        return (year, month, day, sunset_hour, sunset_minute, 0, 0, 0)
    return None

