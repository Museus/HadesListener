#repurposed from https://stackoverflow.com/questions/2408560/non-blocking-console-input/57387909#57387909

import threading
import sys
import os
import contextlib
import signal
from traceback import format_exception_only

def run_lua(s):
    listener.send(prefix + s)

def run_py(s):
    s = s.lstrip()
    try:
        try:
            eval(compile(s, '<string>', 'single'), globals())
        except SyntaxError as e:
            if e.args[0] == "unexpected EOF while parsing":
                eval(compile(s, '<string>', 'exec'), globals())
            else:
                raise SyntaxError from e
    except Exception:
        print(exception_string(),end='')

def exception_string():
    return "".join(format_exception_only(*(sys.exc_info()[:2])))

class KeyboardThread(threading.Thread):

    def __init__(self, input_cbk = None, name='keyboard-input-thread'):
        self.input_cbk = input_cbk
        super(KeyboardThread, self).__init__(name=name)
        self.start()

    def run(self):
        while True:
            self.input_cbk(input()) #waits to get input + Return

def my_callback(inp):
    #evaluate the keyboard input
    if inp:
        if inp[:1] == ">":
            run_py(inp[1:])
        else:
            run_lua(inp)

#start the Keyboard thread
kthread = KeyboardThread(my_callback)

prefix = "HadesListenerREPL: "
def load():
    listener.add_hook(run_py, prefix, __name__)
    listener.ignore_prefixes.append(prefix)

def end():
    try:
        listener.game.terminate()
    except:
        pass
    with contextlib.suppress(FileNotFoundError):
        for path in listener.proxy_purepaths.values():
            os.remove(path)
    os.kill(os.getpid(), signal.SIGTERM)
