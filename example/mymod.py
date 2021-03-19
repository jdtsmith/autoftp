import time
from myothermod import myOtherModule

class myModule:
    def __init__(self, sleep = 500):
        self.sleep = sleep # seconds to sleep
        self.run = True
        self.other = myOtherModule('Other Info')
    
    def start(self):
        i=0
        while i<self.sleep and self.run:
            time.sleep(1)
            if i%3 == 0:
                t = time.localtime()
                print("[{:02d}:{:02d}:{:02d}] Still sleeping".
                      format(*t[3:6]))
                self.other.report()
            i = i+1

    def stop(self):
        self.run = False
