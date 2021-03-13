#!/usr/bin/env python3
# autoftp: auto-send changed files matching a pattern
# 2021, J.D. Smith
import os
import sys
import time
import ftplib
from getopt import gnu_getopt as getopt
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import colorama
colorama.init()
_BRI=colorama.Style.BRIGHT
_RST=colorama.Style.RESET_ALL

def log(msg = None,error = False, prefix = None, **kwds):
    file = sys.stderr if error else None
    if prefix:
        print(prefix, file = file, end = '', flush = True, **kwds)
    if msg:
        col = colorama.Fore.RED if error else colorama.Fore.GREEN
        print(col + msg + colorama.Style.RESET_ALL,file=file, **kwds)

class FTPWatcher(PatternMatchingEventHandler):
    def __init__(self, host, debug = None, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.debug = debug
        self.ftp_start()

    def ftp_start(self):
        if hasattr(self,'ftp'):
            self.ftp.close()
            log(prefix = "== Reconnecting FTP\n")
        try:
            self.ftp = ftplib.FTP(self.host)
        except OSError as e:
            log(f"Could not connect to {self.host}: \n\t{repr(e)}", error = True)
            exit();
        self.ftp.login()
        if self.is_ok():
            pwd = self.ftp.pwd()
            log(prefix = "== FTP server connected: ", msg = f"{self.host} (pwd: {pwd})")
        else:
            raise ConnectionError
        if self.debug:
            self.ftp.set_debuglevel(self.debug)
        
    def is_ok(self):
        try:
            self.ftp.voidcmd("NOOP")
        except (ftplib.error_reply, TimeoutError):
            return False
        finally:
            return True

    def mkdirs(self, subdir):
        cur = ''
        for dr in subdir.split(os.sep):
            if dr == '.': continue
            cur = os.path.join(cur,dr)
            try:
                self.ftp.voidcmd("SIZE " + cur)
            except:
                self.ftp.mkd(cur)

    def on_created(self, event):
        self.handle(event)

    def on_modified(self,event):
        self.handle(event)
        
    def handle(self,event):
        path=event.src_path
        l = time.localtime()
        
        log(prefix=f">> {_BRI}{l.tm_hour:>2}:{l.tm_min:02}{_RST} Processing {_BRI}{path}{_RST}...")
        subdir = None
        tries = 0
        t0 = time.perf_counter()
        while tries<5:
            try:
                if subdir is not None:
                    if not self.is_ok(): raise ConnectionError
                    self.mkdirs(subdir)
                    log("success: ", end = '')
                with open(path,"rb") as f:
                    self.ftp.storbinary("STOR " + path, f)
                log(f"transferred in {_BRI}{time.perf_counter()-t0:.2}s{_RST}")
                break
            except (ConnectionError, TimeoutError, EOFError):
                log("\nFTP connection problem, attempting restart", error = True)
                self.ftp_start()
            except ftplib.error_perm as e:
                if subdir is not None: # already tried subdir creation 
                    log(f"Failed to transfer file {path}, aborting\n\t{repr(e)}",
                        error = True, flush = True)
                    return
                if e.args[0].startswith('550'):
                    subdir = os.path.dirname(path)
                    if subdir != '.':
                        log(f"failed\n>> attempting remote directory creation: {subdir}...",
                            error = True, flush = True, end = '')
                        continue
                log("\nUnhandled FTP error: " + repr(e), error = True)
                return
            tries += 1
        if tries == 5:
            log("FTP re-connect failed, aborting", error = True)

if __name__ == "__main__":
    debug = None
    opts,args = getopt(sys.argv[1:],"p:x:d",["include=",'exclude='])
    if len(args) < 1:
        log("Usage: autoftp ftphost -d --include=|-p 'a,b' --exclude=|-x 'c,d'", error = True)
        log(" ftphost: FTP host to connect to\n"+
            " -d: Enable debugging\n" + 
            " -p|--include='a,b': include patterns of files to match (default: '*.py')\n"+
            " -x|--exclude='c,d': filepath patterns to ignore (e.g. '*lib/*,secret*.py')",
            error = True)
        exit()
    host = args[0]
    pats = ["*.py"]
    expats = None
    for opt,arg in opts:
        if opt in ("--include","-p"):
            pats = [x.strip() for x in arg.split(",")]
        elif opt in ("--exclude","-x"):
            expats = [x.strip() for x in arg.split(",")]
        elif opt == "-d":
            debug = 2

    welcome = "AutoFTP v0.1"
    if debug: welcome += " (debugging enabled)"
    log(prefix = welcome + "\n\n") 
    log(prefix = '== Monitoring files matching: ', msg = "|".join(pats))
    if expats: log(prefix='==  Excluding files matching: ', msg = "|".join(expats))
    log(prefix = "\n")
    
    try:
        ftp_handler = FTPWatcher(host,
                                 patterns = pats, ignore_patterns = expats,
                                 ignore_directories = True,
                                 case_sensitive = True, debug = debug)
        observer = Observer()
        observer.schedule(ftp_handler, '.', recursive=True)
        observer.start()
        while observer.is_alive():
            observer.join(30)
            if not ftp_handler.is_ok(): ftp_handler.ftp_start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        log(prefix = " Quitting AutoFTP...\n")
        try:
            if ftp_handler and ftp_handler.ftp:
                ftp_handler.ftp.quit()
            if observer:
                observer.stop()
                observer.join()
        except (NameError, ConnectionError):
            pass
