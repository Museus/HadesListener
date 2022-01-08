"""
Magic_Gonads (Discord: Magic_Gonads#7347)
Museus (Discord: Museus#7777)
"""
from collections import defaultdict
import os
import sys
import platform
import pathlib
import pkgutil
import importlib.util
import contextlib
from subprocess import Popen, PIPE, STDOUT

# Do not include extension
EXECUTABLE_NAMES = { "hades" : "Hades", "pyre": "Pyre" }
# Do not include leading character (/ or -)
EXECUTABLE_ARGS = ["DebugDraw=true", "DebugKeysEnabled=true", "RequireFocusToUpdate=false"]
PLUGIN_SUBPATH = "StyxScribeScripts"
LUA_PROXY_STDIN = "proxy_stdin.txt"
LUA_PROXY_FALSE = "proxy_first.txt"
LUA_PROXY_TRUE = "proxy_second.txt"
PROXY_LOADED_PREFIX = "StyxScribe: ACK"
INTERNAL_IGNORE_PREFIXES = (PROXY_LOADED_PREFIX,)
OUTPUT_FILE = "game_output.log" 

class StyxScribe:
    """
    Used to launch the game with a wrapper that listens for specified patterns.
    Calls any functions that are added via `add_hook` when patterns are detected.
    """

    class Modules(dict):
        def __getattr__(self, key):
            if self.__dict__.__contains__(key):
                return self.__dict__.__getitem__(key)
            return self.__getitem__(key)
        def __hasattr__(self, key):
            if self.__dict__.__contains__(key):
                return True
            return self.__contains__(key)

    def __init__(self, game="Hades"):
        self.executable_name = EXECUTABLE_NAMES[game.lower()]
        if platform.system() != "Darwin":
            self.executable_purepath = (
                pathlib.PurePath() / "x64" / f"{self.executable_name}.exe"
            )
            self.args = [f"/{arg}" for arg in EXECUTABLE_ARGS]
            self.plugins_paths = [str(
                pathlib.PurePath() / "Content" / PLUGIN_SUBPATH
            )]
        else:
            self.executable_purepath = pathlib.PurePath() / self.executable_name
            self.args = [f"-{arg}" for arg in executable_args]
            self.plugins_paths = [str(
                pathlib.PurePath() / "Contents/Resources/Content" / PLUGIN_SUBPATH
            )]

        self.executable_cwd_purepath = self.executable_purepath.parent
        if self.executable_name == "Pyre":
            self.executable_cwd_purepath = self.executable_cwd_purepath.parent
            
        self.proxy_purepaths = {
            None: self.executable_cwd_purepath / LUA_PROXY_STDIN,
            False: self.executable_cwd_purepath / LUA_PROXY_FALSE,
            True: self.executable_cwd_purepath / LUA_PROXY_TRUE
        }
        
        self.args.insert(0, self.executable_purepath)
        self.hooks = defaultdict(list)
        self.modules = self.Modules()
        self.modules[__name__] = sys.modules[__name__]
        self.ignore_prefixes = list(INTERNAL_IGNORE_PREFIXES)

    def launch(self,echo=True,log=OUTPUT_FILE):
        """
        Launch the game and listen for patterns in self.hooks
        """
        if echo:
            print(f"Running {self.args[0]} with arguments: {self.args[1:]}")

        proxy_switch = False

        def sane(message):
            return f"[===[{message}]===]"

        def quick_write_file(path, content):
            with open(path, 'w', encoding="utf8") as file:
                file.write(content)

        def setup_proxies():
            nonlocal proxy_switch
            quick_write_file(self.proxy_purepaths[None], f"print({sane(PROXY_LOADED_PREFIX)});return {sane(self.proxy_purepaths[proxy_switch].name)}")
            with contextlib.suppress(FileNotFoundError):
                os.remove(self.proxy_purepaths[proxy_switch])
            proxy_switch = not proxy_switch
            quick_write_file(self.proxy_purepaths[proxy_switch], f"print({sane(PROXY_LOADED_PREFIX)});return {sane(self.proxy_purepaths[not proxy_switch].name)}")

        def send(message):
            with open(self.proxy_purepaths[proxy_switch], 'a', encoding="utf8") as file:
                if echo and not message.startswith(tuple(self.ignore_prefixes)):
                    print(f"In: {message}")
                file.write(f",{sane(message)}")
                file.flush()
        self.send = send

        def run(out=None):
            setup_proxies()
                
            self.game = Popen(
                self.args,
                cwd=self.executable_purepath.parent,
                stdout=PIPE,
                stderr=STDOUT,
                universal_newlines=True,
                encoding="utf8",
            )

            while self.game.poll() is None:
                output = self.game.stdout.readline()
                if not output:
                    break
                output = output[:-1]
                if not output.startswith(tuple(self.ignore_prefixes)):
                    if echo:
                        print(f"Out: {output}")
                    if out:
                        print(output, file=out)
                        out.flush()

                if output.startswith(PROXY_LOADED_PREFIX):
                    setup_proxies()

                for prefix, callbacks in self.hooks.items():
                    if output.startswith(prefix):
                        for callback in callbacks:
                            callback(output[len(prefix):])

        if log:
            with open(log, 'w', encoding="utf8") as out:
                run(out)
        else:
            run()

        with contextlib.suppress(FileNotFoundError):
            for path in self.proxy_purepaths.values():
                os.remove(path)

    def add_hook(self, callback, prefix="", source=None):
        """Add a target function to be called when pattern is detected

        Parameters
        ----------
        callback : function
            function to call when pattern is detected
        prefix : str
            pattern to look for at the start of lines in stdout
        """
        if callback in self.hooks[prefix]:
            return  # Function already hooked
        if not callable(callback):
            if source is not None:
                raise TypeError("Callback must be callable, blame {source}.")
            else:
                raise TypeError("Callback must be callable.")
        self.hooks[prefix].append(callback)
        if source is not None:
            callback = f"{callback} from {source}"
        print(f"Adding hook on \"{prefix}\" with {callback}")

    def load_plugins(self):
        for module_finder, name, _ in pkgutil.iter_modules(self.plugins_paths):
            spec = module_finder.find_spec(name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.scribe = self
            self.modules[name] =  module
            if hasattr(module, "load"):
                module.load()
            elif hasattr(module, "callback"):
                self.add_hook(module.callback, getattr(module, "prefix", name + '\t'), name)
