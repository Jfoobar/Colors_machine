import time
import datetime
import subprocess
import csv
import os
import sys

# Configuration
START_DATE = datetime.date(2025, 1, 1)
CSV_FILENAME = 'sunset_data.csv'
RECORDING_DURATION = 180 # 3 minutes in seconds

def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))

def get_day_number(target_date):
    delta = target_date - START_DATE
    return delta.days

def get_sunset_minutes(day_number):
    csv_path = os.path.join(get_script_dir(), CSV_FILENAME)
    try:
        with open(csv_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) == 2 and int(row[0]) == day_number:
                    return int(row[1])
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return None

def control_recorder(command):
    """
    Sends a command to the audio-recorder CLI.
    Valid commands: start, stop, pause, show, hide, quit, status
    """
    print(f"[{datetime.datetime.now()}] Sending command: {command}")
    try:
        subprocess.run(['audio-recorder', '--command', command], check=False)
    except FileNotFoundError:
        print("Error: audio-recorder executable not found.")

def record_for_duration(duration):
    control_recorder('start')
    time.sleep(duration)
    control_recorder('stop')

def main():
    print("Starting Audio Monitor...")
    control_recorder('status') # Check status on startup

    # State tracking to avoid double triggering in the same minute
    triggered_events = {
        '0755': False,
        '0800': False,
        'sunset_minus_5': False,
        'sunset': False,
        '2200': False
    }
    
    current_date = datetime.date.today()
    day_num = get_day_number(current_date)
    sunset_mins = get_sunset_minutes(day_num)
    
    if sunset_mins:
        sunset_time = datetime.time(sunset_mins // 60, sunset_mins % 60)
        print(f"Today's sunset is at {sunset_time.strftime('%H:%M')}")
    else:
        print("Could not find sunset time for today.")

    while True:
        now = datetime.datetime.now()
        today = now.date()
        
        # Reset for new day
        if today != current_date:
            print("New day detected. Resetting flags and reloading sunset.")
            current_date = today
            day_num = get_day_number(current_date)
            sunset_mins = get_sunset_minutes(day_num)
            for k in triggered_events:
                triggered_events[k] = False
            
            if sunset_mins:
                sunset_time = datetime.time(sunset_mins // 60, sunset_mins % 60)
                print(f"Today's sunset is at {sunset_time.strftime('%H:%M')}")
            else:
                print("Could not find sunset time for today.")

        # Calculate current seconds past midnight
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        
        # Define target seconds for fixed events
        # 07:55:00 -> 28500 seconds. Trigger 10s early: 28490
        target_0755 = (7 * 60 + 55) * 60
        if not triggered_events['0755'] and current_seconds >= (target_0755 - 10) and current_seconds < (target_0755 + 60):
            print("Triggering 07:55 Event (First Call) - 10s early")
            record_for_duration(30)
            triggered_events['0755'] = True

        # 08:00:00 -> 28800 seconds. Trigger 10s early: 28790
        target_0800 = 8 * 3600
        if not triggered_events['0800'] and current_seconds >= (target_0800 - 10) and current_seconds < (target_0800 + 60):
            print("Triggering 08:00 Event (Colors) - 10s early")
            record_for_duration(180)
            triggered_events['0800'] = True

        if sunset_mins is not None:
            sunset_seconds = sunset_mins * 60
            
            # Sunset - 5 mins. Trigger 10s early.
            target_sunset_minus_5 = sunset_seconds - (5 * 60)
            if not triggered_events['sunset_minus_5'] and current_seconds >= (target_sunset_minus_5 - 10) and current_seconds < (target_sunset_minus_5 + 60):
                print("Triggering Sunset-5 Event (First Call) - 10s early")
                record_for_duration(30)
                triggered_events['sunset_minus_5'] = True

            # Sunset. Trigger 10s early.
            if not triggered_events['sunset'] and current_seconds >= (sunset_seconds - 10) and current_seconds < (sunset_seconds + 60):
                print("Triggering Sunset Event (Retreat) - 10s early")
                record_for_duration(120)
                triggered_events['sunset'] = True

        # 22:00:00 -> 79200 seconds. Trigger 10s early: 79190
        target_2200 = 22 * 3600
        if not triggered_events['2200'] and current_seconds >= (target_2200 - 10) and current_seconds < (target_2200 + 60):
            print("Triggering 22:00 Event (Taps) - 10s early")
            record_for_duration(120)
            triggered_events['2200'] = True

        # Sleep 1 second for precision
        time.sleep(1)

if __name__ == "__main__":
    main()
