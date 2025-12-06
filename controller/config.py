# Global configuration variables
system_msg = "Booting..."

def get_system_msg():
    global system_msg
    #print("Getting system_msg:", system_msg)
    return system_msg

def set_system_msg(msg):
    global system_msg
    print("Setting system_msg from", system_msg, "to", msg)
    system_msg = msg