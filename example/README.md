# autoftp Auto-Re-running Example

This small example program shows how `autoftp` can be used to accomplish _auto re-running_ of a MicroPythong project.  It includes an updated version of [`uftpd.py`](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD) which supports `exec`'ing code via `SITE` commands.  To try it, edit `.autoftp` to mention your host, `wifi.py` with your wifi details, and transfer all the files to start to the root directory of a clean MicroPython board (using `rshell`, for example).

Once all the files are loaded, soft-reboot (`Ctrl-D`) and you should see the simple module startup.  Now run `autoftp.py` in the 'examples/' directory.  After it connects to the FTP server, try editing any of the `my*.py` files. They should get uploaded, and the `reload_stop('file')` function is exec'd for the relevant `file`. This function unloads the appropriate modules from `sys.modules`, re-imports the main module (and re-assigns the global variable pointing to it), then stops the current running module.

N.B.: whatever command you execute via `autoftp` _must_ return immediately and not block, or the FTP server will become non-responsive.  In this example, that is accomplished using a main module loop that monitors for a stop flag (`self.run`), and a `while True` loop at the end of `main.py` which restarts the module after it stopped.

If you have an unusually deep module import structure, your equivalent of `stop_reload` might need to be more involved, but this example should suffice for many cases.
