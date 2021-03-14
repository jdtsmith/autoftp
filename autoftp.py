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
from pathlib import Path
import subprocess

import colorama
colorama.init()
_BRI=colorama.Style.BRIGHT
_RST=colorama.Style.RESET_ALL

def path_matches(path,patterns, key = None):
    ppath = Path(path) # *destination* must also match
    try:
        match = next(x for x in patterns if ppath.match(x[key] if key else x))
    except StopIteration:
        return None
    else:
        return match

def log(msg = None,error = False, prefix = None, **kwds):
    file = sys.stderr if error else None
    if prefix:
        print(prefix, file = file, end = '', flush = True, **kwds)
    if msg:
        col = colorama.Fore.RED if error else colorama.Fore.GREEN
        print(col + msg + colorama.Style.RESET_ALL,file=file, **kwds)

class FTPWatcher(PatternMatchingEventHandler):
    def __init__(self, host, patterns = None,  process_patterns = None,
                 upload_delete_patterns = None, debug = None, **kwargs):
        patterns = patterns or []
        if process_patterns:
            patterns.extend(x['pattern'] for x in process_patterns)
        super().__init__(patterns = patterns, **kwargs)
        self.process_patterns = process_patterns
        self.upload_delete_patterns = upload_delete_patterns
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

    def on_moved(self, event):
        if path_matches(event.dest_path, self.patterns):
            self.handle(event.dest_path)
        
    def on_created(self, event):
        self.handle(event.src_path)

    def on_modified(self,event):
        self.handle(event.src_path)
        
    def handle(self,path):
        l = time.localtime()
        log(prefix=f">> {_BRI}{l.tm_hour:>2}:{l.tm_min:02}{_RST} Processing {_BRI}{path}{_RST}...")
        ppath = Path(path)

        t0 = time.perf_counter()
        if self.process_patterns:
            match = path_matches(path, self.process_patterns, key = 'pattern')
            if match:
                try:
                    subprocess.run((match['script'], path), check = True)
                except (FileNotFoundError, subprocess.CalledProcessError) as e:
                    log(f"script {match['script']} encountered error:\n" + repr(e), error = True)
                else:
                    log(f"ran script {match['script']} in {_BRI}{time.perf_counter()-t0:.2}s{_RST}")
                return

        subdir = None
        tries = 0
        while tries<5:
            try:
                if subdir is not None:
                    if not self.is_ok(): raise ConnectionError
                    self.mkdirs(subdir)
                    log("success: ", end = '')
                with open(path,"rb") as f:
                    self.ftp.storbinary("STOR " + path, f)
                log(f"transferred in {_BRI}{time.perf_counter()-t0:.2}s{_RST}", end='', flush = True)
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
            else:
                if self.upload_delete_patterns and path_matches(path, self.upload_delete_patterns):
                    os.remove(path)
                    log(" [local file deleted]")
                else:
                    log(prefix = "\n")
                break
            tries += 1
        if tries == 5:
            log("FTP re-connect failed, aborting", error = True)

usage = '''
Usage: autoftp ftphost -d --include=|-p --exclude=|-x --process=|-s --updelete|-k
  ftphost: FTP host to connect to
  -d: Enable debugging output
  -p|--include='pat,pat,...': include patterns of files to match (default: '*.py')
  -x|--exclude='pat,pat,...': filepath patterns to ignore (e.g. '*lib/*,secret*.py')
  -s|--process='pat,script': instead of uploading, run `script' on files matching `pat'
  -k|--updelete='pat,pat,..': filepath patterns to delete after uploading
'''
            
if __name__ == "__main__":
    debug = None
    opts,args = getopt(sys.argv[1:],"p:x:s:k:d",["include=","exclude=","process=","updelete="])
    if len(args) < 1:
        log(usage, error = True)
        exit()
    host = args[0]
    pats = ["*.py"]
    expats, procpats, delpats = [], [], []
    for opt,arg in opts:
        if opt in   ("--include","-p"):
            pats = [x.strip() for x in arg.split(",")]
        elif opt in ("--exclude","-x"):
            expats.extend([x.strip() for x in arg.split(",")])
        elif opt in ("--process","-s"):
            pp = [x.strip() for x in arg.split(",")]
            if len(pp) != 2:
                log("Error in process option: " + usage,error = True)
                exit()
            procpats.append(dict(zip(("pattern","script"),pp)))
        elif opt in ("--updelete","-k"):
            delpats.extend([x.strip() for x in arg.split(",")])
        elif opt == "-d":
            debug = 2

    welcome = "AutoFTP v0.11"
    if debug: welcome += " (debugging enabled)"
    log(prefix = welcome + "\n\n") 
    log(prefix = '== Monitoring files matching: ', msg = ",".join(pats))
    if expats:
        log(prefix='==  Excluding files matching: ', msg = ",".join(expats))
    if procpats:
        log(prefix='== Processing files matching: ',
            msg = ",".join([x['pattern']+':'+x['script'] for x in procpats]))
    if delpats:
        log(prefix='== Deleting uploaded files matching: ', msg = ",".join(delpats))
    log(prefix = "\n")

    log(prefix = f'== Connecting to FTP...\n')
    try:
        ftp_handler = FTPWatcher(host,
                                 patterns = pats, ignore_patterns = expats,
                                 process_patterns = procpats, upload_delete_patterns = delpats,
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
        log(prefix = "\nQuitting AutoFTP...\n")
        try:
            if ftp_handler and ftp_handler.ftp:
                ftp_handler.ftp.quit()
            if observer:
                observer.stop()
                observer.join()
        except (NameError, ConnectionError):
            pass
