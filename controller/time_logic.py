"""Time-related helpers: NTP sync, DS3231 integration, and DST-aware localtime."""
import ntptime
import time
from machine import Pin, I2C, RTC
#import ds3231  # Assuming ds3231.py is in the same directory
from ds3231_port import DS3231

# DS3231 and I2C setup (using the pins from main.py)
I2C_SCL = 14
I2C_SDA = 47
I2C_FREQ = 100000
rtc_i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
ds = DS3231(rtc_i2c)

def sync_ntp_time(ntp_hosts, ntp_retry_delay=0):
    """Sync RTC with NTP and update the DS3231.
    
    Returns True on success, False if all hosts fail.
    """
    for host in ntp_hosts:
        ntptime.host = host
        try:
            print("Trying NTP host:", host)
            ntptime.settime()
            # Get the new time from the internal RTC
            (year, month, mday, hour, minute, second, weekday, yearday) = time.gmtime()
            # Set the DS3231 with the new time
            ds.set_time((year, month, mday, hour, minute, second, weekday, yearday))
            print("Time synchronized via NTP and written to DS3231.")
            return True
        except Exception as e:
            print("NTP sync failed for {}: {}".format(host, e))
            if ntp_retry_delay > 0:
                time.sleep(ntp_retry_delay)
    print("All NTP hosts failed. Check your internet connection or DNS.")
    return False

def get_rtc_time_and_set_internal_rtc():
    #year,month,mday,hour,minute,second,weekday, yearday = 2025, 11, 2, 8, 59, 55 ,7, 305 #test end dst
    #ds.set_time((year, month, mday, hour, minute, second, weekday, yearday))
    """
    Reads time from DS3231 and sets the internal RTC.
    Returns True if successful, False otherwise.
    """
    try:
        ds_time = ds.get_time()
        print(ds_time)
        if not ds_time[0]> 2024:
            print("DS1307 time appears invalid. Internal RTC not set.")
            return False
        
        (year, month, mday, hour, minute, second, weekday, yearday) = ds_time
        rtc = RTC()
        # The weekday returned by DS3231 is 1-7, while MicroPython's RTC is 0-6
        rtc.datetime((year, month, mday, weekday - 1, hour, minute, second, yearday))
        print(time.gmtime())
        print(time.localtime())
        print("Time read from DS3231 and set on internal RTC.")
        return True
    except Exception as e:
        print("Error reading from DS3231:", e)
        print("Internal RTC not set from DS3231.")
        return False


def format_time_str(t):
    """Formats the time tuple into a readable string HH:MM:SS."""
    year, month, mday, hour, minute, second, _, _ = t
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def format_date_str(t):
    """Formats the time tuple into a readable date string MM/DD/YYYY."""
    year, month, mday, _, _, _, _, _ = t
    return f"{month:02d}/{mday:02d}/{year}"


def weekday(year, month, day):
    """Sakamoto's algorithm: return weekday 0=Sunday ... 6=Saturday."""
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    y = year
    if month < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + t[month - 1] + day) % 7


def nth_weekday_of_month(year, month, weekday_target, n):
    """Return the day number of the n-th weekday_target in the month.
    weekday_target: 0=Sunday
    """
    for d in range(1, 8):
        if weekday(year, month, d) == weekday_target:
            return d + (n - 1) * 7
    return None


def is_dst_us(year, month, day, hour=0):
    """Determine if US DST rules (current) are in effect for the given date/time.
    Spring forward: 2 AM jumps to 3 AM (2:00-2:59 never happens)
    Fall back: At 2 AM falls back to 1 AM (1:00-1:59 happens twice)
    """
    start_day = nth_weekday_of_month(year, 3, 0, 2)  # 2nd Sunday in March
    end_day = nth_weekday_of_month(year, 11, 0, 1)   # 1st Sunday in November
    
    if month == 11 and day == end_day and hour == 1: #comparing base utc offset hour not dst adjusted hour
            # At exactly 2 AM dst, fall back to 1 AM standard time
            return False
    
    #this works for all other times including spring forward gap
    now = year * 1000000 + month * 10000 + day * 100 + hour  #Year gets multiplied by 1,000,000 (6 decimal places)
    start = year * 1000000 + 3 * 10000 + start_day * 100 + 2 #Month gets multiplied by 10,000 (4 decimal places)
    end = year * 1000000 + 11 * 10000 + end_day * 100 + 2 #Day gets multiplied by 100 (2 decimal places)
    #Hour stays as is. Now we can compare a number instead of multiple fields
    return start <= now < end  


def localtime_with_optional_dst(utc_offset_seconds, enable_dst=True):
    """Return a localtime tuple adjusted for utc_offset_seconds and optional DST."""
    ts = time.time()
    base = time.localtime(ts + utc_offset_seconds)
    if not enable_dst:
        return base

    y, m, d, hh = base[0], base[1], base[2], base[3]
    if is_dst_us(y, m, d, hh):
        return time.localtime(ts + utc_offset_seconds + 3600)
    return base


def set_manual_time(year, month, day, hour, minute, second):
    """Sets the DS3231 and internal RTC with the given time."""
    try:
        # Calculate weekday (0=Monday...6=Sunday for mktime, but we need 1-7 for DS3231?)
        # DS3231: 1-7. Sakamoto's weekday returns 0=Sunday...6=Saturday.
        # Let's use the existing weekday function
        wd = weekday(year, month, day) 
        # weekday() returns 0=Sunday, 1=Monday...
        # DS3231 expects 1-7. Usually 1=Sunday or 1=Monday. 
        # Let's assume 1=Sunday to match the 0=Sunday of our helper + 1.
        ds_weekday = wd + 1
        
        yearday = 0 # Not strictly needed for basic timekeeping
        
        ds.set_time((year, month, day, hour, minute, second, ds_weekday, yearday))
        
        rtc = RTC()
        # MicroPython RTC: 0=Monday, 6=Sunday. 
        # Our weekday() is 0=Sunday, 1=Monday... 6=Saturday.
        # So MP_RTC_WD = (wd - 1) % 7
        mp_weekday = (wd - 1) % 7
        
        rtc.datetime((year, month, day, mp_weekday, hour, minute, second, 0))
        print(f"Manual time set: {year}-{month}-{day} {hour}:{minute}:{second}")
        return True
    except Exception as e:
        print(f"Error setting manual time: {e}")
        return False

def get_current_minutes_past_midnight(utc_offset_s, enable_dst=True):
    """Return the current local time in minutes past previous midnight."""
    tmin = localtime_with_optional_dst(utc_offset_s, enable_dst)
    return tmin[3] * 60 + tmin[4]


__all__ = [
    "sync_ntp_time",
    "get_rtc_time_and_set_internal_rtc",
    "format_time_str",
    "format_date_str",
    "localtime_with_optional_dst",
    "get_current_minutes_past_midnight",
    "set_manual_time",
]
