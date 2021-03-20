#!/usr/bin/env python3
# autoftp: auto-send changed files matching a pattern, with script and remote
#          commands processing
# External Dependencies: colorama, watchdog
# (c) 2021, J.D. Smith
import os
import sys
import time
import ftplib
from getopt import GetoptError, gnu_getopt as getopt
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from pathlib import Path
import subprocess

import colorama
colorama.init()
_BRI = colorama.Style.BRIGHT
_RST = colorama.Style.RESET_ALL
_GREEN = colorama.Fore.GREEN
__VERSION__='v0.2'

def path_matches(path,patterns, key = None):
    if patterns:
        ppath = Path(path) # *destination* must also match
        try:
            match = next(x for x in patterns if ppath.match(x[key] if key else x))
        except StopIteration:
            return None
        else:
            return match

def log(msg = None, error = False, dry_run = False, prefix = None, **kwds):
    file = sys.stderr if error else None
    if prefix:
        print(prefix, file = file, end = '', flush = True, **kwds)
    if msg:
        if error:
            col = colorama.Fore.RED
        elif dry_run:
            col = colorama.Fore.BLUE
        else:
            col = colorama.Fore.GREEN
        print(col + msg + colorama.Fore.RESET,file=file, **kwds)
    if not prefix and not msg:
        print("")

def cur_time():
    l = time.localtime()
    return f"{_BRI}{l.tm_hour:02}:{l.tm_min:02}:{l.tm_sec:02}{_RST}"

        
class FTPWatcher(PatternMatchingEventHandler):
    def __init__(self, config, **kwargs):
        patterns = config["include"] or []
        if config["process"]:
            patterns.extend(x['pattern'] for x in config["process"])
        super().__init__(patterns = patterns, **kwargs)
        self.host = config["host"]
        self.config = config
        self.ftp_start()

    def ftp_start(self, max_tries = 3):
        if hasattr(self,'ftp') and self.ftp:
            self.ftp.close()
            log(prefix = "==  Reconnecting FTP... \n")
        tries = 0
        while tries < max_tries:
            try:
                self.ftp = ftplib.FTP(self.host)
            except ConnectionError as e:
                exc = e
                tries += 1
                time.sleep(1)
            else:
                break
                
        if tries == max_tries:
            log(prefix = "==  ",
                msg = f"Could not connect to {self.host}: \n\t{repr(exc)}", error = True)
            exit();

        self.ftp.login()
        if self.is_ok():
            pwd = self.ftp.pwd()
            log(prefix = "==  FTP server connected: ", msg = f"{self.host} (pwd: {pwd})")
        else:
            raise ConnectionError
        if self.config["debug"]:
            self.ftp.set_debuglevel(2)
        
    def is_ok(self):
        try:
            self.ftp.voidcmd("NOOP")
        except (ftplib.error_reply, ftplib.error_perm, TimeoutError, EOFError, ConnectionError):
            return False
        else:
            return True

    def mkdirs(self, subdir):
        cur = ''
        for dr in subdir.split(os.sep):
            if dr == '.': continue
            cur = os.path.join(cur,dr)
            try:
                self.ftp.voidcmd("SIZE " + cur) # Exists?
            except:
                self.ftp.mkd(cur)

    def on_moved(self, event):
        if path_matches(event.dest_path, self.config["include"]):
            self.handle(event.dest_path)
        
    def on_created(self, event):
        self.handle(event.src_path)

    def on_modified(self,event):
        self.handle(event.src_path)
        
    def handle(self,path):
        if not os.path.isfile(path): return # Ignore phantom modified on delete
        log(prefix=f">> {cur_time()} Processing {_BRI}{path}{_RST}...")
        ppath = Path(path)

        t0 = time.perf_counter()

        # Script-process file and return
        match = path_matches(path, self.config["process"], key = 'pattern')
        if match:
            try:
                subprocess.run((match['script'], path), check = True)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                log(f"script {match['script']} encountered error:\n\t{repr(e)}", error = True)
            else:
                log(f"ran script {match['script']} in {_BRI}{time.perf_counter()-t0:.2}s{_RST}")
            return

        # Upload file, optionally remove, and possibly execute remote command
        subdir = None
        tries = 0
        while tries<5:
            try:
                if subdir is not None:
                    if not self.is_ok(): raise ConnectionError
                    self.mkdirs(subdir)
                    log("success: ", end = '')
                if self.config["dry-run"]:
                    log("would have uploaded", dry_run = True, end = '', flush = True)
                else: 
                    with open(path,"rb") as f:
                        self.ftp.storbinary("STOR " + path, f)
                    log(f" transferred in {_BRI}{time.perf_counter()-t0:.2}s{_RST}",
                        end='', flush = True)
            except (ConnectionError, TimeoutError, EOFError):
                log(prefix = "\n==  ",
                    msg = "FTP connection problem, attempting restart...", error = True)
                self.ftp_start()
            except ftplib.error_perm as e:
                if subdir is not None: # already tried subdir creation 
                    log(f"Failed to transfer file {path}, aborting:\n\t{repr(e)}",
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
            else: # Successfully uploaded path!
                if path_matches(path, self.config["up-delete"]):
                    if config["dry-run"]:
                        log(" [would have deleted]", dry_run = True)
                    else:
                        os.remove(path)
                        log(" [local file deleted]")
                else:
                    log()
                if self.config["remote-command"] and (not self.config["remote-match"] or
                                                      path_matches(path, self.config["remote-match"])):
                    cmd = self.config["remote-command"]
                    cmd = cmd.replace('%%f', os.path.basename(path).split('.')[0])
                    if config["dry-run"]:
                        cmd = '\t' + cmd.replace('\0','\n\t')
                        log(prefix = "** ",msg = f"Would have run command:\n{cmd}",
                            dry_run = True)
                    else:
                        try:
                            self.ftp.voidcmd("SITE " + cmd)
                        except (ftplib.error_reply, ftplib.error_perm) as e:
                            cmd = '\t' + cmd.replace('\0','\n\t')
                            log(error = True, prefix = "** ",
                                msg = f"Remote command failed:\n{cmd}\n\t" + repr(e))
                        else:
                            cmd = '\t' + cmd.replace('\n','\n\t')
                            log(prefix = "** Ran remote command:\n", msg = cmd)
                return
            tries += 1
        if tries == 5:
            log("FTP re-connect failed, file not transfered, aborting", error = True)

usage = '''
Usage: autoftp host -d|--debug -n|--dry-run -p|--include=pats -x|--exclude=pats 
                    -s|--process=pat,script -k|--up-delete=pats
  host: FTP host to connect to
  -d|--debug: Enable debugging output
  -n|--dry-run: Uploads and local deletes are logged, but do not occur
  -p|--include='pat,pat,...': include patterns of files to match for upload
                              (default: '*.py')
  -x|--exclude='pat,pat,...': patterns to ignore (e.g. '*lib/*,secret*.py')
  -s|--process='pat,script' : instead of uploading, run `script' on each file
                              matching `pat' (can pass multiple times)
  -k|--up-delete='pat,pat,..': delete files match any of the patterns, after
                              they have been successfully uploaded
  -r|--remote-command='command': command to execute on the remote (ftp) server 
                              after each uploaded file. %%f will be replaced by 
                              the file basename of the uploaded file
  -m|--remote-match='pat,pat': only execute --remote-command on uploaded
                              files which match one of these patterns

Options can also be specified in a `.autoftp' file in the current directory, 
using the format:

host: hostname
long-option-name
long-option-with-value-name: value

one option per line (omitting the leading dashes).  No quotes are required.  
N.B.: options passed via the command line override & extend file-based options.
'''

if __name__ == "__main__":
    import re

    def read_config_file(config):
        in_remote = False
        with open(".autoftp","r") as f:
            for line in f:
                line = line.rstrip()
                for k,v in config.items():
                    if type(v) is bool:
                        match = re.match(fr'^{k}\s*',line)
                        if match:
                            config[k] = True
                            in_remote = False
                            break
                    else:
                        match = re.match(fr'^{k}:\s*',line)
                        if match:
                            in_remote = (k == 'remote-command')
                            arg=line[match.end():]
                            if arg:
                                if k in ('host','remote-command'):
                                    config[k] = arg
                                elif k == 'process':
                                    pp = [x.strip() for x in arg.split(",")]
                                    if len(pp) != 2:
                                        log(error = True,
                                            msg = "Error in .autoftp process option: " + usage)
                                        exit()
                                    config[k].append(dict(zip(("pattern","script"),pp)))
                                elif k in ('include','exclude','up-delete','remote-match'):
                                    config[k].extend([x.strip() for x in arg.split(",")])
                            break
                if not match and in_remote: # Unmatching lines in remote get added
                    if config['remote-command']:
                        config['remote-command'] += '\0' + line
                    else:
                        config['remote-command'] = line

    welcome = f"{_BRI}AutoFTP {__VERSION__}{_RST}"
    extra_welcome = []
    config = {"host": None,
              "debug": False,
              "dry-run": False,
              "include": [],
              "exclude": [],
              "process": [],
              "up-delete": [],
              "remote-command": None,
              "remote-match": []}

    #Process .autoftp file options
    if os.path.isfile(".autoftp"):
        extra_welcome.append("reading .autoftp config")
        read_config_file(config)
    
    # Process command line options
    if len(sys.argv) > 1:
        try:
            opts,args = getopt(sys.argv[1:],"p:x:s:k:r:m:dn",
                               ["include=","exclude=","process=","up-delete=",'remote-command=',
                                'remote-match=',"debug","dry-run"])
        except GetoptError:
            log(usage, error = True)
            exit()
        if args:
            config['host'] = args[0]

        for opt,arg in opts:
            if opt in   ("--include", "-p"):
                config["include"].extend([x.strip() for x in arg.split(",")])
            elif opt in ("--exclude", "-x"):
                config["exclude"].extend([x.strip() for x in arg.split(",")])
            elif opt in ("--process", "-s"):
                pp = [x.strip() for x in arg.split(",")]
                if len(pp) != 2:
                    log("Error in process option: " + usage,error = True)
                    exit()
                config["process"].append(dict(zip(("pattern","script"),pp)))
            elif opt in ("--up-delete", "-k"):
                config["up-delete"].extend([x.strip() for x in arg.split(",")])
            elif opt in ("--remote-command", "-r"):
                config["remote-command"] = arg
            elif opt in ("--remote-match", "-m"):
                config["remote-match"].extend([x.strip() for x in arg.split(",")])
            elif opt in ("--dry-run", "-n"):
                config["dry-run"] = True
            elif opt in ("--debug", "-d"):
                config["debug"] = True

    if not config["host"]:
        log("Hostname required. " + usage, error = True)
        exit();
    if not config["include"]: config["include"] = ["*.py"]
        
    # Welcome Splash
    if config["debug"]:
        extra_welcome.append("debugging enabled")
    if config["dry-run"]:
        extra_welcome.append(colorama.Fore.BLUE +
                             "dry-run" +
                             (": only script processing occurs" if config["process"] else "") +
                             _RST)

    if extra_welcome:
        welcome += " (" + ", ".join(extra_welcome) + ")"
    log(prefix = welcome + "\n\n")

    log(prefix = '%% Monitoring files matching: ', msg = ",".join(config["include"]))
    if config["exclude"]:
        log(prefix='%% Excluding files matching: ', msg = ",".join(config["exclude"]))
    if config["process"]:
        log(prefix='%% Processing files matching: ',
            msg = ",".join([x['pattern']+':'+x['script'] for x in config["process"]]))
    if config["up-delete"]:
        log(prefix='%% Deleting uploaded files matching: ', msg = ",".join(config["up-delete"]))
    if config["remote-command"]:
        pref = '%% Running remote command after upload'
        if config["remote-match"]:
           pref += " of files matching: "
           pref += _GREEN + ",".join(config["remote-match"]) + _RST
        log(prefix=pref + ': \n', msg = '\t' + config["remote-command"].replace('\0','\n\t'))
            
    log(prefix = '\n== Connecting to FTP...\n')
    try:
        ftp_handler = FTPWatcher(config, ignore_directories = True, case_sensitive = True)
        observer = Observer()
        observer.schedule(ftp_handler, '.', recursive=True)
        observer.start()
        while observer.is_alive():
            observer.join(30)
            if not ftp_handler.is_ok():
                log(prefix = f"== {cur_time()} ",
                    msg = "FTP connection problem, attempting restart...", error = True)
                ftp_handler.ftp_start()
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
        except (NameError, ConnectionError, AttributeError, EOFError):
            pass
