# autoftp

Watch for changes in files with matching names in the current directory and all subdirectories.  For any matching files which are created or modified files, quickly send them by FTP to a remote server.

## Quick Start

```
% pip install colorama watchdog
% autoftp host
```

Install the [`uftpd.py`](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD) micro-FTP server on your micro-controller, and set it up to run on your controller (see below for tips).

`autoftp` will start monitoring for changes in any `.py` files in the local directory or below, sending the files via an actively maintained FTP session to `host` whenever they are created or modified, and creating sub-directories as needed. 

## Usage

```
Usage: autoftp host -d --include=|-p 'a,b' --exclude=|-x 'c,d'
 -d: Enable debugging
 -p|--include='a,b': include patterns of files to match (default: '*.py')
 -x|--exclude='c,d': filepath patterns to ignore (e.g. '*lib/*,secret*.py')
```

`Ctrl-C` to quit.  

Only files are watched and uploaded.  All files must match the `-p` wildcard pattern (`*.py` by default), and must _not_ match any `-x` exclude pattern(s).  The latter is a good way to omit entire directories, etc.  By default, files are placed in directories relative to the FTP server's working directory (typically the root of the microcontroller if started from `boot.py`).

## Micropython Application

Micro-controller development can be tedious.  With C-based firmware frameworks, you must:

1. Make a tiny change, perhaps to a single constant in some file
1. Recompile [1-30s]
1. Relink the firmware [1-10s]
1. Upload the firmware over Serial [>10s]
1. Wait for microcontroller to reboot and re-run firmware
1. Test your changes

An edit/compile/build/upload test cycle over one minute is not atypical. 

[Micropython](http://micropython.org) greatly simplifies this workflow.  It includes an interactive REPL for testing and development.  But for typical projects, you'll be editing relatively large Python files (>5K), in which case the development loop can _still_ be a somewhat slow process:

1. Make a tiny change, perhaps to a single constant in some file
1. Using a tool like [rshell](https://github.com/dhylands/rshell), `C-x` to exit REPL, use `cp file.py /board` to upload file over serial port [~15s for a 25K file]
1. Wait for microcontroller to reboot, and reinitialize (perhaps by hand) [1-5s, e.g. for Wifi startup]
1. Test your changes

This can still result in a 10-30s development loop time.  `autoftp` enables a much faster workflow for network-connected microcontrollers:

1. Make a tiny change, perhaps to a single constant
1. File changes are noticed and immediately uploaded to micro-controller [0.5s for small file, <1s for files <25K]
1. Reload code and test

## Questions

1. **Where does `autoftp` put files?** FTP servers have a common 

## Tips

### Starting WiFi and `uftpd`

Typical for an ESP32 or related device.

in `boot.py`:
```
#Start ftp server
import wifi
wifi.start()
import uftpd
```

in `wifi.py`:
```# Connect wifi and set host
import time
import network

HOSTNAME="myhost"
SSID='MYSSID'
PASSWORD='MYPASSWD'
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
```



