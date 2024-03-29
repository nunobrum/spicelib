#!/usr/bin/env python
# coding=utf-8

"""Helper script to be able to insert validated code into the README.md file."""
import os
import sys
import re
from shutil import copyfile

# Read the README.md on the path indicated on the command line arguments
filename = sys.argv[1]

readme_md = open(filename).readlines()

in_statement_regex = re.compile(r"-- in (?P<path>.*?)(?P<loc>\s\[.*\])?$")

block_start = -1
line_no = 0
# detect python code blocks
while line_no < len(readme_md):
    line = readme_md[line_no]
    if "```python" in line:
        block_start = line_no
    elif "```" in line and block_start != -1:
        # check whether the next line has the -- in statement
        if line_no + 1 < len(readme_md):
            m = in_statement_regex.search(readme_md[line_no + 1])
            # find the file to include
            if m:
                include_relpath = m.group("path")
                include_path = os.path.abspath(os.path.join(os.curdir, include_relpath))
                include_text = open(include_path, "r", encoding="utf-8").readlines()
                # if there is a localization, isolate only the part identified by loc
                # the part starts with "# -- Start of <loc> --" and ends with "# -- End of <loc> --"
                # where <loc> is the text within the square brackets [] in the readme.md
                if (loc := m.group("loc")) is not None:
                    lines_to_plug = []
                    loc_text = loc[2:-1]  # This is crude but it works. It removes the leading \s[ and the trailing ]
                    start_tag = "-- Start of %s --" % loc_text
                    end_tag = "-- End of %s --" % loc_text
                    include_ident = -1
                    for line1 in include_text:
                        if start_tag in line1:
                            include_ident = line1.find("#")  # This marks the indent of all the block
                        elif end_tag in line1:
                            include_ident = -1
                        else:
                            if include_ident >= 0:  # means that we are reading between the Start and End
                                if include_ident >= len(line1):  # if it is a blank line
                                    lines_to_plug.append("")  # Add a blank line
                                else:
                                    lines_to_plug.append(line1[include_ident:])
                else:
                    lines_to_plug = include_text
                existing_lines = line_no - (block_start + 1)  # This accounts for the start and finish ``` line
                new_lines = len(lines_to_plug)
                readme_md[block_start + 1:line_no] = lines_to_plug
                line_no += new_lines - existing_lines
    line_no += 1

# Finally write back the readme.md but first create a backup
copyfile(filename, filename.replace(".md", ".bak"))
open(filename, 'w').writelines(readme_md)
exit(0)
