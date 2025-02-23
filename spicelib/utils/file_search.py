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
from typing import Optional
import logging

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

_logger = logging.getLogger("spicelib.Utils")


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


def search_file_in_containers(filename, *containers) -> Optional[str]:
    """
    Searches for a file with the given filename in the specified containers.
    Returns the path to the file if found, or None if not found.
    
    :param filename: file name to search (posix string)
    :type filename: str
    :param containers: list of paths to search in (posix strings)
    :type containers: List[str]
    :return: path to the file if found, or None if not found.
    :rtype: Optional[str]
    """
    for container in containers:
        _logger.debug(f"Searching for '{filename}' in '{container}'")
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
                            _logger.debug(f"Found. Extracting '{filefound}' from the zip file to '{temp_dir}'")
                            return zip_ref.extract(filefound, path=temp_dir)
            else:
                filefound = find_file_in_directory(container, filename)
                if filefound is not None:
                    _logger.debug(f"Found '{filefound}'")
                    return filefound
    _logger.debug(f"Searching for '{filename}': NOT Found")
    return None
