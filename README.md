# autoftp — Fast remote development over FTP

Auto-send matching files over the network with FTP.  Watches for changes in files with matching names in the current directory and all subdirectories, quickly sending them by FTP to a remote server.  While this works with any files and remote FTP server, it is ideal for network-connected microcontroller development.

Click to see `autoftp` in action:
<div align="left">
      <a href="https://www.youtube.com/watch?v=FaDdorOd11E">
         <img src="https://img.youtube.com/vi/FaDdorOd11E/0.jpg" style="width:100%">
      </a>
</div>

## Quick Start

```
% pip install colorama watchdog
% autoftp host
```

Install the [`uftpd.py`](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD) micro-FTP server on your micro-controller, and set it up to run on your controller (see below for tips).

Install the [`autoftp`](https://raw.githubusercontent.com/jdtsmith/autoftp/master/autoftp.py) file and run it like you normally run your Python3 scripts. 

To use, just run in a directory like `autoftp host`.  `autoftp` will start monitoring for changes in any `.py` files (by default) in the local directory or below, sending the files via an actively maintained FTP session to `host` whenever they are created or modified, creating any sub-directories as needed. 

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

An edit/compile/build/upload "development loop" cycle over one minute is not atypical. Painful!

[Micropython](http://micropython.org) greatly simplifies this workflow.  It includes an interactive REPL for testing and development. It's _paste mode_ (`Ctrl-E`) makes testing small chunks of code trivial.  But for typical projects, you'll be editing and uploading relatively large Python files (>5K).  In this case, the development loop can _still_ be a somewhat slow process:

1. Make a tiny change, perhaps to a single constant in some file
1. Using a tool like [rshell](https://github.com/dhylands/rshell): `C-x` to exit the REPL, `cp file.py /board` to upload file over serial port [~15-20s for a 25K file at the default baud rate]
1. Wait for microcontroller to reboot (which the rshell `cp` causes), and then reinitialize (perhaps by hand) [1-5s, e.g. for Wifi startup]
1. Test your changes

So this still looks like a 10-30s "development loop" time.  `autoftp` enables a _much faster_ workflow for network-connected microcontrollers:

1. Make a tiny change, perhaps to a single constant
1. File changes are noticed and automatically and immediately uploaded to the micro-controller [0.5s for small file, <1s for files <25K]
1. Reload code and test

## Questions

1. **Where does `autoftp` put the files?** FTP servers have a _current working directory_ (mentioned at `autoftp` startup). For a typical installation this will be `/`, the root of your micro-controller's flash.  Files in the directory where `autoftp` is run from go into the current working directory; files in subdirectories go into matching subdirectories (which are created if necessary). 

1. **Won't this wear out the flash?** Unlikely.  Flash usually is written with _wear-leveling_ to spread the writes around, and can support ~100,000 writes without error.  If you edit and re-upload a 5K file (about 150 lines of Python) every 10 seconds 10hrs/day, this works out to 1.3 million writes per year, or just over 1600 full re-writes of a typical (ESP32) 4MB of flash.  At this rate, it would take **62 years** to surpass the 100,000 write limit: a pretty good safety margin.  Another perspective: it may take a fixed number of code/upload/check cycles to bring a project into stability; `autoftp` just accelerates that process. 

1. **Why not just use an FTP client?** In fact I used to use `ncftpput`, which can automatically find changed files and upload them.  But it adds 1-2s minimum extra overhead as it re-negotiates the FTP connection each time.  `autoftp` takes that friction entirely away. 

## Tips

## Installing uftpd

[`uftpd.py`](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD) is a small uftpd server which runs in the background waiting for socket connections.  To install, just drop the `uftpd.py` file on your microcontroller (perhaps in the `lib/` subdirectory). 

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



