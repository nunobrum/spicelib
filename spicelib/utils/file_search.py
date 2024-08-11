# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        file_search.py
# Purpose:     Tools for searching files on libraries
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     28-03-2024
# Licence:     refer to the LICENSE file
#
# -------------------------------------------------------------------------------
import os
import zipfile
import sys


__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"


def find_file_in_directory(directory, filename):
    """
    Searches for a file with the given filename in the specified directory and its subdirectories.
    Returns the path to the file if found, or None if not found.
    """
    # First check whether there is a path tagged to the filename
    path, filename = os.path.split(filename)
    if path != '':
        directory = os.path.join(directory, path)
    for root, dirs, files in os.walk(directory):
        # match case insensitive, but store the file system's file name, as the file system may be case sensitive
        for filefound in files:
            if filename.lower() == filefound.lower():
                return os.path.join(root, filefound)
    return None


def search_file_in_containers(filename, *containers):
    """
    Searches for a file with the given filename in the specified containers.
    Returns the path to the file if found, or None if not found.

    """
    for container in containers:
        # print(f"Searching for {filename} in {os.path.abspath(container)}")
        if os.path.exists(container):  # Skipping invalid paths
            if container.endswith('.zip'):
                # Search in zip files
                with zipfile.ZipFile(container, 'r') as zip_ref:
                    files = zip_ref.namelist()
                    for filefound in files:
                        # match case insensitive, but store the file system's file name, as the file system may be case sensitive
                        if filename.lower() == filefound.lower():
                            temp_dir = os.path.join('.', 'spice_lib_temp')
                            if not os.path.exists(temp_dir):
                                os.makedirs(temp_dir)
                            return zip_ref.extract(filefound, path=temp_dir)
            else:
                file_found = find_file_in_directory(container, filename)
                if file_found is not None:
                    return file_found
    return None


def expand_and_check_local_dir(path: str, exe_path: str = None) -> str:
    """
    Expands a directory path to become an absolute path, while taking into account a potential use under wine (under MacOS and Linux). 
    Will also check if that directory exists.
    The path must either be an absolute path or start with ~. Relative paths are not supported.
    On MacOS or Linux, it will try to replace any reference to the virtual windows root under wine into a host OS path.
    
    Examples:
    * under windows:
      * C:/mydir -> C:/mydir
      * ~/mydir -> C:/Users/myuser/mydir
    * under linux, and if the executable is /mywineroot/.wine/drive_c/(something):
      * C:/mydir -> /mywineroot/.wine/drive_c/mydir
      * ~/mydir -> /mywineroot/.wine/drive_c/users/myuser/mydir
    
    :param path: The path to expand. Must be in posix format, use `PureWindowsPath(path).as_posix()` to transform a windows path to a posix path.
    :type path: str
    :param exe_path: path to a related executable that may or may not be under wine, defaults to None, ignored on Windows
    :type exe_path: str, optional
    :return: the fully expanded path, as posix path, will return None if the path does not exist.
    :rtype: str
    """
    c_drive = None
    if sys.platform == "linux" or sys.platform == "darwin":
        if exe_path and "/drive_c/" in exe_path:
            # this is very likely a wine path
            c_drive = exe_path.split("/drive_c/")[0] + "/drive_c/"
    if c_drive is not None:
        # this must be linux or darwin, with wine
        if path.startswith("~"):
            # Normally, a large number of directories in the home directory of a user under wine are symlinked 
            # to the user's home directory in the host OS. That would mean, that "~/Documents" under wine is 
            # normally also "~/Documents" under the host OS. But this is not always the case, and not for all directories. 
            # The user can have modified this, via for example a winetricks sandbox.
            # Therefore, I make it an absolute path for Windows and do not try to optimise:
            path = "C:/users/" + os.path.expandvars("${USER}" + path[1:])  
            # If I were to do this expansion under Windows, I should use ${USERNAME} but we're not in Windows here. 
            # I also cannot use expanduser(), as that again would be for the wrong OS.
            # All lowercase "users" is correct, as it is the default path for the user's home directory in wine.
        # I now have a "windows" path (but in posix form, with forward slashes). Make it into a host OS path.
        if path.startswith("C:/") or path.startswith("c:/"):
            path = c_drive + path[3:]  # should start with C:. If not, something is wrong. 
        # note that in theory, the exe path can be relative to the user's home directory, so...
    # and in all cases, terminate with the expansion of the ~
    if path.startswith("~"):
        path = os.path.expanduser(path)
        
    # check existance and if it is a directory
    if os.path.exists(path) and os.path.isdir(path):
        return path
    return None
