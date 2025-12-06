import network
import socket
import ure
import time
import machine
import time_logic

ap_ssid = "WifiManager"
ap_password = "password" # You might want to change this
ap_authmode = 3 # WPA2
NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

server_socket = None
addr = None

def get_connection():
    """return a working WLAN(STA_IF) instance or None"""

    # First check if there already is any connection:
    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        time.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        # Read known network profiles from file
        profiles = read_profiles()

        # Search WiFis in range
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
            if encrypted:
                if ssid in profiles:
                    password = profiles[ssid]['password']
                    connected = do_connect(ssid, password)
                else:
                    print("skipping unknown encrypted network")
            else:  # open
                connected = do_connect(ssid, None)
            if connected:
                break

    except OSError as e:
        print("exception", str(e))

    return wlan_sta if connected else None


def read_profiles():
    try:
        with open(NETWORK_PROFILES) as f:
            lines = f.readlines()
        profiles = {}
        for line in lines:
            parts = line.strip("\n").split(";")
            if len(parts) >= 2:
                ssid = parts[0]
                password = parts[1]
                ntp = parts[2] if len(parts) > 2 else None
                profiles[ssid] = {'password': password, 'ntp': ntp}
        return profiles
    except OSError:
        return {}


def has_profiles():
    profiles = read_profiles()
    return len(profiles) > 0


def write_profiles(profiles):
    lines = []
    for ssid, data in profiles.items():
        password = data['password']
        ntp = data.get('ntp')
        if ntp:
             lines.append("%s;%s;%s\n" % (ssid, password, ntp))
        else:
             lines.append("%s;%s\n" % (ssid, password))
    with open(NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


def get_connected_ntp():
    """Returns the custom NTP server for the currently connected network, or None."""
    if not wlan_sta.isconnected():
        return None
    try:
        ssid = wlan_sta.config('essid')
        profiles = read_profiles()
        if ssid in profiles:
            return profiles[ssid].get('ntp')
    except:
        pass
    return None


def do_connect(ssid, password):
    wlan_sta.active(True)
    if wlan_sta.isconnected():
        return None
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)
    for retry in range(200):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected. Network config: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


def send_header(client, status_code=200, content_length=None):
    client.sendall("HTTP/1.0 {} OK\r\n".format(status_code))
    client.sendall("Content-Type: text/html\r\n")
    if content_length is not None:
        client.sendall("Content-Length: {}\r\n".format(content_length))
    client.sendall("\r\n")


def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        client.sendall(payload)
    client.close()


def handle_root(client):
    wlan_sta.active(True)
    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    send_header(client)
    client.sendall("""\
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; margin: 20px; }
                    table { margin: auto; }
                    input[type=text], input[type=password], input[type=number] { padding: 5px; margin: 5px; }
                    input[type=submit] { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                    h1 { color: #5e9ca0; }
                </style>
            </head>
            <body>
                <h1>WiFi & Time Setup</h1>
                <form action="configure" method="post">
                    <h3>Select WiFi Network</h3>
                    <table>
        """)
    while len(ssids):
        ssid = ssids.pop(0)
        client.sendall("""\
                        <tr>
                            <td colspan="2">
                                <input type="radio" name="ssid" value="{0}" />{0}
                            </td>
                        </tr>
        """.format(ssid))
    client.sendall("""\
                        <tr>
                            <td>Password:</td>
                            <td><input name="password" type="password" /></td>
                        </tr>
                        <tr>
                            <td>Custom NTP (Optional):</td>
                            <td><input name="custom_ntp" type="text" placeholder="10.98.0.6" /></td>
                        </tr>
                    </table>
                    <hr/>
                    <h3>Set Current Time</h3>
                    <p><input type="checkbox" name="set_time" value="1"> Update Time</p>
                    <p>Use GMT time to set, firmware will convert to Pacific Time.</p>
                    <table>
                        <tr><td>Year:</td><td><input name="year" type="number" value="2025" style="width:60px"></td></tr>
                        <tr><td>Month:</td><td><input name="month" type="number" value="1" min="1" max="12" style="width:60px"></td></tr>
                        <tr><td>Day:</td><td><input name="day" type="number" value="1" min="1" max="31" style="width:60px"></td></tr>
                        <tr><td>Hour (24h):</td><td><input name="hour" type="number" value="12" min="0" max="23" style="width:60px"></td></tr>
                        <tr><td>Minute:</td><td><input name="minute" type="number" value="0" min="0" max="59" style="width:60px"></td></tr>
                        <tr><td>Second:</td><td><input name="second" type="number" value="0" min="0" max="59" style="width:60px"></td></tr>
                    </table>
                    <br/>
                    <input type="submit" value="Save & Connect" />
                </form>
            </body>
        </html>
        """)
    client.close()


def unquote(string):
    """unquote('abc%20def') -> b'abc def'."""
    if not string:
        return b''
    
    if isinstance(string, str):
        string = string.encode('utf-8')
        
    res = string.split(b'%')
    if len(res) == 1:
        return string
        
    s = res[0]
    for item in res[1:]:
        try:
            s += bytes([int(item[:2], 16)]) + item[2:]
        except:
            s += b'%' + item
    return s

def handle_configure(client, request):
    # Parse WiFi credentials
    match_wifi = ure.search("ssid=([^&]*)&password=([^&]*)", request)
    match_ntp = ure.search("custom_ntp=([^&]*)", request)
    
    # Parse Time (optional, but expected if form submitted)
    # Regex is tricky with variable params, so let's try to find them individually or in a block
    # The form sends: ssid=...&password=...&year=...&month=...
    
    # Let's just extract everything we can
    ssid = ""
    password = ""
    custom_ntp = None
    
    if match_wifi:
        try:
            ssid = unquote(match_wifi.group(1)).decode("utf-8")
            password = unquote(match_wifi.group(2)).decode("utf-8")
        except Exception as e:
            print("Error parsing credentials: ", e)
            ssid = match_wifi.group(1).decode("utf-8")
            password = match_wifi.group(2).decode("utf-8")
            
    if match_ntp:
        try:
            custom_ntp = unquote(match_ntp.group(1)).decode("utf-8")
            if len(custom_ntp) == 0:
                custom_ntp = None
        except:
            pass
    
    # Try to parse time fields
    time_set = False
    
    # Check if set_time checkbox was checked
    should_set_time = ure.search("set_time=1", request)
    
    if should_set_time:
        try:
            year = int(ure.search("year=([0-9]+)", request).group(1))
            month = int(ure.search("month=([0-9]+)", request).group(1))
            day = int(ure.search("day=([0-9]+)", request).group(1))
            hour = int(ure.search("hour=([0-9]+)", request).group(1))
            minute = int(ure.search("minute=([0-9]+)", request).group(1))
            second = int(ure.search("second=([0-9]+)", request).group(1))
            
            print(f"Setting time to: {year}-{month}-{day} {hour}:{minute}:{second}")
            if time_logic.set_manual_time(year, month, day, hour, minute, second):
                time_set = True
        except Exception as e:
            print(f"Time parsing failed or not provided: {e}")
    else:
        print("Time update not requested.")

    if len(ssid) == 0:
        if time_set:
            # Manual time set, no SSID -> Offline Mode
            handle_continue_offline(client)
            return True # Signal to exit AP loop (treated as success/handled)
        else:
            send_response(client, "SSID or manual time checkbox select must be provided", status_code=400)
            return False

    if do_connect(ssid, password):
        response = """\
            <html>
                <center>
                    <br><br>
                    <h1 style="color: #5e9ca0;">Connected!</h1>
                    <p>ESP successfully connected to WiFi network %(ssid)s.</p>
                    <p>Time updated if provided.</p>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        time.sleep(1)
        wlan_ap.active(False)
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = {'password': password, 'ntp': custom_ntp}
        write_profiles(profiles)
        time.sleep(5)
        return True
    else:
        response = """\
            <html>
                <center>
                    <h1 style="color: #5e9ca0;">Connection Failed</h1>
                    <p>ESP could not connect to WiFi network %(ssid)s.</p>
                    <form>
                        <input type="button" value="Go back!" onclick="history.back()"></input>
                    </form>
                    <br>
                    <form action="continue_offline" method="post">
                         <input type="submit" value="Continue Offline" style="background-color: #f44336;" />
                    </form>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        return False


def handle_continue_offline(client):
    response = """\
        <html>
            <center>
                <br><br>
                <h1 style="color: #5e9ca0;">Offline Mode</h1>
                <p>Proceeding without WiFi connection...</p>
            </center>
        </html>
    """
    send_response(client, response)
    time.sleep(1)
    wlan_ap.active(False)


def handle_not_found(client, url):
    send_response(client, "Path not found: {}".format(url), status_code=404)


def stop():
    global server_socket
    if server_socket:
        server_socket.close()
        server_socket = None


def start(port=80):
    global server_socket, addr
    # Clean up any previous socket state first
    stop()
    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

    wlan_sta.active(True)
    wlan_sta.disconnect() # Force disconnect to ensure we stay in AP mode
    wlan_ap.active(True)
    wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)
    
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(addr)
    server_socket.listen(1)
    print('Connect to WiFi ssid ' + ap_ssid + ', password: ' + ap_password)
    print('and access the ESP via your favorite web browser at 192.168.4.1.')
    print('Listening on:', addr)
    
    try:
        while True:
            if wlan_sta.isconnected():
                wlan_ap.active(False)
                return True
            
            try:
                # Use select or timeout to avoid blocking forever so we can check the 10-min timer
                server_socket.settimeout(1.0) 
                client, addr = server_socket.accept()
                print('client connected from', addr)
                
                client.settimeout(5.0)
                request = b""
                try:
                    while "\r\n\r\n" not in request:
                        request += client.recv(512)
                except OSError:
                    pass
                
                # Handle form data (POST body)
                try:
                    if "POST" in request.decode('utf-8', 'ignore'):
                         # Read content length if possible, or just read some more
                         request += client.recv(1024)
                except OSError:
                    pass

                print("Request is: {}".format(request))
                request_str = request.decode("utf-8", "ignore")
                
                if "HTTP" not in request_str:
                    client.close()
                    continue
                
                try:
                    url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request_str).group(1).rstrip("/")
                except Exception:
                    url = ""
                    
                print("URL is {}".format(url))
                if url == "":
                    handle_root(client)
                elif url == "configure":
                    if handle_configure(client, request_str):
                        return True
                elif url == "continue_offline":
                    handle_continue_offline(client)
                    return False # Return False to indicate no WiFi, but exit loop
                else:
                    handle_not_found(client, url)
                    
            except OSError as e:
                # Timeout from accept() is expected
                pass
    finally:
        stop()
