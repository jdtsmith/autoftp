# Connect wifi and set host
import time
import network

HOSTNAME="esp32"
SSID='MYSSID'
PASSWORD='MYPWD'
wlan = network.WLAN(network.STA_IF)

def activate(timeout=10):
    wlan.active(True)
    for _ in range(5):
        try:
            wlan.config(dhcp_hostname=HOSTNAME)
        except OSError:
            time.sleep_ms(500)

    start=time.ticks_ms()
    
    if not wlan.isconnected():
        wlan.connect(SSID,PASSWORD) 
        while not wlan.isconnected():
            time.sleep_ms(150)
            if time.ticks_diff(time.ticks_ms(),start)/1e3 > timeout: break
    
def start(quiet=False,log_callback=None):
    for i in range(1,11):
        if not quiet: print('connecting to network{}...'.
                            format(" [{}]".format(i) if i>1 else ""))
        activate()
        if wlan.isconnected(): break
        if log_callback: log_callback(i)
        time.sleep_ms(500)
    if not wlan.isconnected():
        print("Failed to connect wifi!")
        return(None)

    if not quiet: print(HOSTNAME,'network config:', wlan.ifconfig())
    return(wlan)
