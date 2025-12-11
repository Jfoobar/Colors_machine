# Import necessary modules
from machine import Pin, I2C, UART
import ssd1306
import time_logic  # Import own time_logic module
import wifimgr
import sunset  # Import own sunset module
import config    # Import config module for shared variables

# User-defined variables
utc_offset = -8 * 3600  # PST is UTC-8. Adjust for your timezone in seconds.
baud_rate = 9600

# NTP configuration: prioritized list of servers to try for time sync.
ntp_hosts = [
    "pool.ntp.org",
    "time.google.com",
    "time.cloudflare.com",
    "time.nist.gov",
]
ntp_retry_delay = 1

# Whether to apply DST adjustments in local time calculations. Set in main.
enable_dst = True

# I2C and OLED setup using your specified pins
i2c = I2C(scl=Pin(14), sda=Pin(47))
oled_width = 128
oled_height = 64

try:
    oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)
except Exception as e:
    print(f"Error initializing OLED: {e}")
    oled = None

# UART setup for communication with the other ESP32
uart2 = UART(2, baudrate=baud_rate, tx=Pin(41), rx=Pin(38)) #connect TX41 to RX21 on other ESP32 and RX38 to TX22 on other ESP32

# sync_ntp_time and formatting functions moved to time_logic.py and imported above.

def main():
    # Setup Manual AP Button (Pin 40, Pull Up)
    ap_button = Pin(40, Pin.IN, Pin.PULL_UP)
    # Setup Sunset Toggle Switch (from other ESP32)
    sunset_switch = True
    # Check if we have WiFi profiles
    if not wifimgr.has_profiles():
        print("No WiFi profiles found. Starting AP mode...")
        config.set_system_msg("Setup WiFi")
        if oled:
            oled.fill(0)
            oled.text("Setup WiFi", 0, 0)
            oled.text("Connect to AP", 0, 20)
            oled.show()
        wifimgr.start()
    
    # Attempt to connect to Wi-Fi for initial NTP sync
    print("Attempting to connect to WiFi...")
    if wifimgr.get_connection():
        # Check for custom NTP
        custom_ntp = wifimgr.get_connected_ntp()
        if custom_ntp:
            print(f"Using custom NTP: {custom_ntp}")
            current_ntp_hosts = [custom_ntp] + ntp_hosts
        else:
            current_ntp_hosts = ntp_hosts
            
        sync_success = time_logic.sync_ntp_time(current_ntp_hosts, ntp_retry_delay)
        if not sync_success:
            print("NTP sync failed on startup. Checking DS3231.")
            config.set_system_msg("NTP failed")
            if not time_logic.get_rtc_time_and_set_internal_rtc():
                print("DS3231 failed. Time is unsynchronized.")
                config.set_system_msg("DS3231 fail")
    else:
        print("No WiFi connection. Will rely on DS3231.")
        if not time_logic.get_rtc_time_and_set_internal_rtc():
            print("DS3231 failed. Time is unsynchronized.")
            config.set_system_msg("DS3231 fail")

    # --- Main Clock Loop ---
    last_ntp_sync_time = time_logic.time.time()
    ntp_sync_interval = 3600  # 1 hour in seconds
    
    last_wifi_retry_time = time_logic.time.time()
    wifi_retry_interval = 1800 # 30 minutes
    
    start_date_tuple = sunset.START_DATE_TUPLE
    day_num_today = sunset.get_day_number(start_date_tuple)
    sunset_minutes = sunset.get_sunset_minutes(day_num_today)
    
    display_sunset_hrs = None
    display_sunset_mins = None
    
    if sunset_minutes is None:
        print("Sunset data not found for today. Using default schedule.")
        config.set_system_msg("Sunset data N/A")
    else:
        five_min_before_sunset = sunset_minutes - 5
        display_sunset_hrs = sunset_minutes//60
        display_sunset_mins = (sunset_minutes%60)
        new_msg = f"Sunset: {display_sunset_hrs:02}:{display_sunset_mins:02}"
        print("Initial sunset message:", new_msg)
        config.set_system_msg(new_msg)
    action_flags = {
        '0755': False,
        '0800': False,
        'five_min_before_sunset': False,
        'sunset': False,
        '2200': False
    }
    # OLED displayTimer setup
    displayTimer = 0
    
    while True:
        # Check Manual AP Button
        if not ap_button.value(): # Active Low
            print("Manual AP Button Pressed. Entering AP Mode...")
            config.set_system_msg("AP Mode")
            if oled:
                oled.fill(0)
                oled.text("AP Mode", 0, 0)
                oled.show()
            wifimgr.start()
            
            
        # Check for hourly NTP sync (only if connected)
        if wifimgr.wlan_sta.isconnected():
            if time_logic.time.time() - last_ntp_sync_time > ntp_sync_interval:
                print("Hourly NTP sync triggered.")
                
                # Check for custom NTP
                custom_ntp = wifimgr.get_connected_ntp()
                if custom_ntp:
                    current_ntp_hosts = [custom_ntp] + ntp_hosts
                else:
                    current_ntp_hosts = ntp_hosts
                    
                if time_logic.sync_ntp_time(current_ntp_hosts, ntp_retry_delay):
                    last_ntp_sync_time = time_logic.time.time()
                else:
                    print("Hourly NTP sync failed.")
                    last_ntp_sync_time = time_logic.time.time()  # Avoid repeated attempts until next hour
        else:
            # WiFi Retry Logic (every 30 mins if not connected)
            if time_logic.time.time() - last_wifi_retry_time > wifi_retry_interval:
                print("30-minute WiFi retry triggered.")
                if wifimgr.get_connection():
                    print("WiFi reconnected!")
                    
                    # Check for custom NTP
                    custom_ntp = wifimgr.get_connected_ntp()
                    if custom_ntp:
                        current_ntp_hosts = [custom_ntp] + ntp_hosts
                    else:
                        current_ntp_hosts = ntp_hosts
                        
                    if time_logic.sync_ntp_time(current_ntp_hosts, ntp_retry_delay):
                        last_ntp_sync_time = time_logic.time.time()
                else:
                    print("WiFi retry failed.")
                last_wifi_retry_time = time_logic.time.time()
        
        # Get the current time with the timezone offset for display
        t = time_logic.localtime_with_optional_dst(utc_offset, enable_dst=True)
        current_minutes = time_logic.get_current_minutes_past_midnight(utc_offset, enable_dst=True)

        if display_sunset_hrs is not None:
            new_msg = f"Sunset: {display_sunset_hrs:02}:{display_sunset_mins:02}"
            config.set_system_msg(new_msg)
            # --- Time-based action logic ---
        if not action_flags['0755'] and current_minutes == 7 * 60 + 55:
            uart2.write("2\n")
            action_flags['0755'] = True

        if not action_flags['0800'] and current_minutes == 8 * 60:
            uart2.write("0\n")
            action_flags['0800'] = True

        if sunset_minutes is not None and not action_flags['five_min_before_sunset'] and current_minutes == five_min_before_sunset and sunset_switch:
            uart2.write("2\n")
            action_flags['five_min_before_sunset'] = True

        if sunset_minutes is not None and not action_flags['sunset'] and current_minutes == sunset_minutes and sunset_switch:
            uart2.write("3\n")
            action_flags['sunset'] = True
        
        if not action_flags['2200'] and current_minutes == 22 * 60:
            uart2.write("1\n")
            action_flags['2200'] = True
            
            # Check if all daily actions have been completed
        if all(action_flags.values() or time_logic.get_current_minutes_past_midnight(utc_offset) >= 23.9 * 60):
            print("All daily actions sent. Waiting for midnight...")
            # Sleep until the next day (e.g., reset flags at 00:01)
            # You might use a more advanced timer or a deep sleep here.
            while time_logic.get_current_minutes_past_midnight(utc_offset) < 1:
                time_logic.time.sleep(60) # Wait in 1 minute increments near midnight
            #todo : better way to wait until next day without busy waiting
            # Reset flags for the new day
            for key in action_flags:
                action_flags[key] = False
            # Re-fetch sunset time for the new day
            day_num_today = sunset.get_day_number(sunset.START_DATE_TUPLE)
            sunset_minutes = sunset.get_sunset_minutes(day_num_today)
            if sunset_minutes is not None:
                five_min_before_sunset = sunset_minutes - 5
                display_sunset_hrs = sunset_minutes//60
                display_sunset_mins = (sunset_minutes%60)
                new_msg = f"Sunset: {display_sunset_hrs:02}:{display_sunset_mins:02}"
                print("Setting system msg to:", new_msg)
                config.set_system_msg(new_msg)
            else:
                print("Setting system msg to: Sunset data N/A")
                config.set_system_msg("Sunset data N/A")
       # Display time and date on OLED
        if oled:
            time_str = time_logic.format_time_str(t)
            date_str = time_logic.format_date_str(t)
            oled.fill(0)
            if not (uart2.any() and displayTimer == 0):
                oled.text(config.get_system_msg(), 0, 0)
            #set oled size to 2x for time display
            oled.size = 4
            oled.text(time_str, 0, 20)
            oled.size = 1
            oled.text(date_str, 0, 50)
            oled.show()

        # Check for incoming serial data from the other ESP32
        if uart2.any():
            try:
                received_data = uart2.readline()
                if received_data:
                    print("Received from other ESP32:", received_data.decode().strip())
                    if oled:
                        oled.fill(0)
                        oled.text("From Other ESP32:", 0, 0)
                        oled.text(received_data.decode().strip(), 0, 20)
                        oled.show()
                        displayTimer = time_logic.time.ticks_ms()
                    if received_data.decode().strip() == "Auto_Sunset_Toggle":
                        sunset_switch = not sunset_switch
                        print("Sunset switch state:", sunset_switch)
            except Exception as e:
                print(f"Error reading UART data: {e}")
        if displayTimer > 0 and (time_logic.time.ticks_ms() - displayTimer) >= 5000:
            displayTimer = 0

        time_logic.time.sleep(1)

# Run the main logic
if __name__ == "__main__":
   main()
