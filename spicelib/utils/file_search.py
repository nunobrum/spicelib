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
        if filename in files:
            return os.path.join(root, filename)
    return None