import time
from myothermod import myOtherModule

class myModule:
    def __init__(self, sleep = 500):
        self.sleep = sleep # seconds to sleep
        self.run = True
        self.other = myOtherModule('MOM_INFO')
    
    def start(self):
        i=0
        while i<self.sleep and self.run:
            time.sleep(1)
            i = i+1
            if i%5 == 0:
                print("Still sleepy...")
                self.other.report()

    def stop(self):
        self.run = False
