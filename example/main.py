import sys
import wifi
wifi.start()
import uftpd
import mymod

def unload(mod): 
    if not isinstance(mod, (list, tuple)): mod = (mod,)
    for m in mod:
        mod_name = m if type(m) is str else m.__name__
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    return mod_name

# Called from autoftp, reload then stops relevant module. MUST NOT BLOCK!
def reload_stop(mod): 
    if mod == 'mymod':
        unload(mod)
    else:
        unload((mod,'mymod'))
    global mymod
    mymod = __import__('mymod') 
    if mmod: mmod.stop()

def start():
    global mmod
    mmod = mymod.myModule()
    mmod.start()

print(">> myModule: Initial Startup!")
while True:
    start()
    print(">> myModule Stopped, Re-starting!")
