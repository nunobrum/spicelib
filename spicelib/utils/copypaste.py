#!/usr/bin/env python
# coding=utf-8

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# -------------------------------------------------------------------------------
# Name:        copypaste.py
# Purpose:     Implementation agnostic copy-paste wrapper
#
# Author:      Jay Morgan (the-moog@gmx.co.uk)
#
# Created:     21-07-2025
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from __future__ import annotations
import importlib, importlib.util
import logging
from typing import Any
from types import ModuleType
from dataclasses import dataclass, field
from abc import ABCMeta, abstractmethod
import sys

_logger = logging.getLogger("spicelib.utils.copypaste")

__author__ = "Jay Morgan <github: the-moog>"
__copyright__ = "Copyright 2025, Cambridge, UK"


@dataclass
class _CopyPasteInterface_:
    """
    A internal helper class to store metadata about CopyPaste foreign implementations
    """
    name : str
    module : ModuleType|None = None
    spec : object|None = None
    parent : CopyPaste|None = None
    __adapter__ : AdapterBase = field(init=False)

    def __bool__(self) -> bool:
        return all(x is not None for x in (self.module, self.spec, self.parent))

    def __post_init__(self, *args, **kw):
        self._init_adapter_()

    @property
    def adapter_name(self):
        return  f"Adapt{self.name.capitalize()}"
    
    def _init_adapter_(self): 
        if self.module is None:
            _logger.info(f"Copy paste implementation {self.name} not found, using a null interface adapter")
            self.__adapter__ = AdaptNone(self.parent)
            return
        _logger.debug(f"Initalising interface adapter for {self.name}")
        try:
            mod = sys.modules[self.__module__]
            cls = getattr(mod, self.adapter_name)
        except AttributeError:
            _logger.info(f"I could not find an adapter for module {self.name}, you must define an adapter class with the name {self.adapter_name}")
        else:
            self.__adapter__ = cls(self.parent)

    @property
    def adapter(self): 
        return self.__adapter__


class AdapterBase(metaclass=ABCMeta):
    """
    Abstract base class for CopyPaste interface adapter implementations
    """
    parent = None
    function_map = None

    def __init__(self, parent=None):
        if parent is None:
            raise ValueError("No parent defined")
        if not issubclass(parent, CopyPaste):
            raise ValueError("Parent must be a subclass of CopyPaste")        
        self.parent = parent
        if self.function_map is not None:


    def adapter_wrapper(self, func):
        """
        Wrap the foreign call to ensure it always returns something or None
        and optionally prevent it raising exceptions, affecting this callers program flow
        We use a wrapper to save repeated identical code
        """
        def __adapter_wrapper__(*args:tuple, **kw:dict):
            # Wrapper for copy/paste functions that captures errors in 
            # a way to prevent implemtation related errors from affecting
            # application program flow
            if self.parent is None:
                # No copypaste?
                # Log an error
                _logger.error(self.__err__not_available__)
                #if self.raise_on_error:
                #    raise ImportError(self.__err__not_available__)
                #return None
            try:
                retobj = func(self, *args, **kw)
            except Exception as er:
                # Something went wrong, not our problem....
                _logger.error(str(er))
                #if self.raise_on_error:
                #    raise(er)
                retobj = None
            return retobj
        return __adapter_wrapper__
    
    # You can't @decorate wrap an @abstractmethod
    # but you can capture it's name lookup within the subclass
    # and emulate a decorator
    def __getattribute__(self, name):
        if name in ("copy", "paste", "cut", "clear"):
            func = getattr(type(self), name)
            return self.adapter_wrapper(func)
        return object.__getattribute__(self, name)

    @abstractmethod
    def copy(self, data: Any)->None:
        """
        Place supplied object(s) from application onto the clipboard.
        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def paste(self)->object:
        """
        Place data from the clipboard into an object and return it to the application
        :return: some object
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        """
        Delete the contents of the clipboard, return true if reading the clipboard returns None or ""
        i.e. true if the clipboard was cleared otherwise false
        :return: bool
        """
        raise NotImplementedError
    
    @abstractmethod
    def cut(self, data:Any)->bool:
        """
        As copy, but return True if the object was placed onto the clipboard
        We first clear the clipboard, then we test this by reading the pasted 
        data and ensuring it is not empty.
        We can't just compare the data as it may be the same but formatted in another way.
        A return of True indicates to the calling app that it is safe to remove
        the cut data from it's memory as a copy exists on the clipboard.
        If the copied data does not match or the clipboard was not first cleared,
        then False is returned, telling the app not to remove the cut data from it's memory.
        """
        raise NotImplementedError
    
    def adapter(func):
        def __wrap_adapter__(self, *args, **kw):
            if self.parent is None:
                raise ValueError("No parent defined")
            if self.parent.interface is None:
                raise ValueError("No interface defined")
            ret = func(*args, **kw)
            return ret
        return __wrap_adapter__

# Adapters for each foreign module
# This wraps our interface round their methods
# It could be as simple as just the original 'module' method, unaltered
# or another new function that adapts the call and/or manipulates the data
#
# NOTE: Adapters must be derived from AdapterBase and
#       have the name in the form of:
#   "Adapt"+implementing_module.__name__.capitalise()
# e.g  "AdaptSomeforeignimplementation"
# Only the 'A' in Adapt and the 'S' in Someforeignimplementation are upper case characters
# this conforms with naming conventions for Python classes
class AdaptPaperclip(AdapterBase):

    def copy(self, data: Any):
        return self.parent.interface.module.copy(data)

    def paste(self):
        return self.parent.interface.module.paste()

    def clear(self):
        raise NotImplementedError("Paperclip does not support a clear() method")

    def cut(self, data:Any)->bool:
        raise NotImplementedError("Paperclip does not support a cut() method")

# Dummy class to make errors soft
class AdaptNone(AdapterBase):


    def copy(self, data: Any):
        raise NotImplementedError("No implementation for copy()")

    def paste(self):
        raise NotImplementedError("No implementation for paste()")

    def clear(self):
        raise NotImplementedError("No implementation for clear()")

    def cut(self, data:Any)->bool:
        raise NotImplementedError("No implementation for cut()")

class AdaptCutpaste(AdapterBase):
    function_map = {'cut': 'cutpaste.cut',
                    'paste': 'cutpaste.paste'}

    def copy(self, data: Any):
        return self.parent.interface.module.copy(data)

    def paste(self):
        return self.parent.interface.module.paste()

    def clear(self):
        raise NotImplementedError("Cutpaste does not support a clear() method")

    def cut(self, data:Any)->bool:
        raise NotImplementedError("Cutpaste does not support a cut() method")

class CopyPaste:
    """
    Implementation agnostic copy-paste
    """

    # List of modules to try in order of preference
    modules = ("paperclip", "cutpaste")

    # Implemented:
    #   https://pypi.org/project/paperclip/
    #   
    #
    # TODO: Allow user customisation of priority
    #   others to consider (not yet implemented)
    # e.g.
    #   https://github.com/terryyin/clipboard
    #   
    interface : _CopyPasteInterface_
    
    __err__not_available__ = """
    No Copy-Paste implementation could be imported
    use """ + " or ".join(f"'pip install {mod}'" for mod in modules)

    def __new__(cls, *args, **kw):
        obj = super().__new__(cls)
        
        # Try loading supported modules
        cls.load_modules(obj)
        
        return obj

    def __init__(self, raise_on_error:bool=False, debuglevel=logging.CRITICAL):
        self.raise_on_error = raise_on_error
        _logger.setLevel(debuglevel)

    @classmethod
    def load_modules(cls, self) -> None:
        """
        Given a list of possible modules to try, find one that works
        """
        chosen = None
        options = {module_name:cls.__try_loading__(module_name) for module_name in cls.modules}
        # More than one implementation, choose paperclip
        if all(options.values()):
            # Prefer paperclip as currently the most recently updated
            chosen = options['paperclip']
            module_name = 'paperclip'
        elif any(options):
            # Not all available, so choose one
            possible = [thisone for thisone,thismodule in options.items() if thismodule]
            if possible:
                module_name = possible[0]
                chosen = options[module_name]
        else:
            # No options
            _logger.warning(cls.__err__not_available__)

        cls.interface = chosen# type: ignore

    
    @classmethod
    def __try_loading__(cls, name:str) -> object:
        """
        Try to load a named module and return that module if it exists
        the module is returned in the form of a _CopyPasteInterface_ object
        that expresses other information not in the foreign code
        :return:_CopyPasteInterface_
        """
        module = None
        spec = None
        if name in sys.modules:
            _logger.debug(f"Using existing module: {name}")
            module = sys.modules[name]
        else:
            spec = importlib.util.find_spec(name)
            if spec is not None:
                # NOTE If the foreign module does not publish the names of it's functions
                # then the import will import the module namespace without the actual functions
                # use the function_map class attribute to create a mapping
                _logger.debug(f"Attempting to load module: {name}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
#                module = importlib.import_module(name)
            else:
                _logger.debug(f"Could not locate module: {name}")
        return _CopyPasteInterface_(name, module, spec, cls)
    

    @property
    def exists(self) -> bool:
        """
        Query if a copy-paste implementation is available
        :return: bool
        """
        return self.interface == True

    @property
    def will_raise(self) -> bool:
        """
        Query if a lack of cut-paste or cut paste itself will raise an error
        :return: bool
        """
        return self.raise_on_error

    @will_raise.setter
    def will_raise(self, raise_on_error:bool):
        """
        Set raise_on_error
        If set to true, then a lack of cut paste or a cut paste action will raise
        If set to false, then the raise will be hidden and None returned by cut paste.
        """
        self.raise_on_error = raise_on_error
    
    def check_interface(func):
        def __check_interface_wrapper__(self, *args, **kw):
            if not self.interface:
                raise ValueError("Interface is not defined")
            if not self.interface.module:
                raise ValueError("Interface has no module")
            return func(self, *args, **kw)
        return __check_interface_wrapper__

    @check_interface
    def copy(self, obj:Any) -> None:
        """
        Place supplied object(s) from application onto the clipboard.
        :return: None
        """
        return self.interface.adapter.copy(obj)

    @check_interface
    def paste(self) -> Any:
        """
        Place data from the clipboard into an object and return it to the application
        :return: some object
        """
        return self.interface.adapter.paste()

    @check_interface
    def clear(self) -> bool:
        """
        Delete the contents of the clipboard
        :return: bool
        """
        return self.interface.adapter.clear()

    # Not wrapped - no need
    def cut(self, obj: Any) -> Any|None:
        """
        As copy, but return True if the object was placed onto the clipboard
        We first clear the clipboard, then we test this by reading the pasted 
        data and ensuring it is not empty.
        We can't just compare the data as it may be the same but formatted in another way.
        A return of True indicates to the calling app that it is safe to remove
        the cut data from it's memory as a copy exists on the clipboard.
        If the copied data does not match or the clipboard was not first cleared,
        then False is returned, telling the app not to remove the cut data from it's memory.
        """
        cleared = self.clear()
        self.copy(obj)
        data = self.paste()
        return cleared and data is not None


if __name__ == "__main__":
    def test_copy_paste():
        
        cp = CopyPaste(debuglevel=logging.DEBUG)
        print("Paste: ", cp.paste())
        cp.copy("Testing 123")
        print("Paste: ", cp.paste())
        if cp.clear():
            print("Clipboard cleared")
        else:
            print("Could not clear clipboard")
        print("Paste: ", cp.paste())
        # Place data onto the clipboard
    
    test_copy_paste()
