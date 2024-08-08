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
        if filename.lower() in [x.lower() for x in files]:
            return os.path.join(root, filename)
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
                    # lower case the name list to facilitate matching
                    if filename.lower() in [x.lower() for x in files]:
                        temp_dir = os.path.join('.', 'spice_lib_temp')
                        if not os.path.exists(temp_dir):
                            os.makedirs(temp_dir)
                        return zip_ref.extract(filename, path=temp_dir)
            else:
                file_found = find_file_in_directory(container, filename)
                if file_found is not None:
                    return file_found
    return None
