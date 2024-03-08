#!/usr/bin/env python
# coding=utf-8
import logging
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        asc_to_qsch.py
# Purpose:     Convert an ASC file to a QSCH schematic
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-02-2024
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import os
import xml.etree.ElementTree as ET

from spicelib.editor.asy_reader import AsyReader
from spicelib.editor.base_schematic import ERotation
from spicelib.editor.asc_editor import AscEditor
from spicelib.editor.qsch_editor import QschEditor, QschTag

_logger = logging.getLogger()


def find_file_in_directory(directory, filename):
    """
    Searches for a file with the given filename in the specified directory and its subdirectories.
    Returns the path to the file if found, or None if not found.
    """
    for root, dirs, files in os.walk(directory):
        if filename in files:
            return os.path.join(root, filename)
    return None


def main():
    """Converts an ASC file to a QSCH schematic"""
    import sys
    import os.path

    if len(sys.argv) < 2:
        print("Usage: asc_to_qsch ASC_FILE [QSCH_FILE]")
        sys.exit(-1)

    asc_file = sys.argv[1]
    if len(sys.argv) > 2:
        qsch_file = sys.argv[2]
    else:
        qsch_file = os.path.splitext(asc_file)[0] + ".qsch"

    print(f"Using {qsch_file} as output file")

    # Open the ASC file
    asc_editor = AscEditor(asc_file)

    # import the conversion data from xml file
    # need first to find the file. It is in the same directory as the script
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    xml_file = os.path.join(parent_dir, 'asc_to_qsch_data.xml')
    conversion_data = ET.parse(xml_file)

    # Get the root element
    root = conversion_data.getroot()

    # Get the offset and scaling
    offset = root.find('offset')
    offset_x = float(offset.get('x'))
    offset_y = float(offset.get('y'))
    scale = root.find('scaling')
    scale_x = float(scale.get('x'))
    scale_y = float(scale.get('y'))

    # Scaling the schematic
    asc_editor.scale(offset_x=offset_x, offset_y=offset_y, scale_x=scale_x, scale_y=scale_y)

    # Adding symbols to components
    symbols = {sym.find('LT_name').text: sym for sym in root.findall('component_symbols/symbol')}
    for comp in asc_editor.components.values():
        symbol_tree = symbols.get(comp.symbol)
        symbol_tag = None
        if symbol_tree is None:
            # Will try to get it from the sym folder
            for sym_root in (
                os.path.expanduser(r"~/AppData/Local/LTspice/lib/sym"),
                os.path.expanduser(r"~\AppData\Local\Programs\ADI\LTspice\lib.zip"),
                "A stupid test directory that doesn't exist and that should be skipped"
            ):
                if not os.path.exists(sym_root):  # Skipping invalid paths
                    continue
                if sym_root.endswith('.zip'):  # TODO: test if it is a file
                    pass  # TODO: implement this
                    # Using an IO buffer to pass the file to the AsyEditor
                else:
                    symbol_asc_file = find_file_in_directory(sym_root, comp.symbol + '.asy')
                if symbol_asc_file is not None:
                    symbol_asc = AsyReader(symbol_asc_file)
                    value = comp.attributes.get('Value', '<val>')
                    symbol_tag = symbol_asc.to_qsch(comp.reference, value)
                    break

        if symbol_tree:
            name = symbol_tree.find("name").text
            offset = symbol_tree.find('LT_origin')
            offset_x = int(offset.get('x'))
            offset_y = int(offset.get('y'))

            if comp.rotation == ERotation.R0:
                comp.position.X += offset_x
                comp.position.Y += offset_y
            elif comp.rotation == ERotation.R90:
                comp.position.X += offset_y
                comp.position.Y -= offset_x
            elif comp.rotation == ERotation.R180:
                comp.position.X -= offset_x
                comp.position.Y -= offset_y
            elif comp.rotation == ERotation.R270:
                comp.position.X -= offset_y
                comp.position.Y += offset_x
            elif comp.rotation == ERotation.M0:
                comp.position.X += offset_x
                comp.position.Y -= offset_y
            elif comp.rotation == ERotation.M90:
                comp.position.X -= offset_y
                comp.position.Y -= offset_x
            elif comp.rotation == ERotation.M180:
                comp.position.X -= offset_x
                comp.position.Y += offset_y
            elif comp.rotation == ERotation.M270:
                comp.position.X += offset_y
                comp.position.Y += offset_x
            rotation = symbol_tree.find('rotation').text
            if rotation == 'R0':
                pass  # basically do nothing
            elif rotation == 'R90':
                comp.rotation = comp.rotation + ERotation.R90
            elif rotation == 'R180':
                comp.rotation = comp.rotation + ERotation.R180
            elif rotation == 'R270':
                comp.rotation = comp.rotation + ERotation.R270
            elif rotation == 'M0':
                comp.rotation = comp.rotation.mirror_x_axis()
            elif rotation == 'M90':
                comp.rotation = comp.rotation  # TODO
            elif rotation == 'M180':
                comp.rotation = comp.rotation.mirror_y_axis()
            elif rotation == 'M270':
                comp.rotation = comp.rotation  # TODO

            # typ = symbol_tree.find("type").text
            # description = symbol_tree.find("description").text

            symbol_tag = QschTag("symbol", name)
            # symbol_tag.items.append(QschTag("type", typ))
            # symbol_tag.items.append(QschTag("description:", description))
            for item in symbol_tree.findall('items/item'):
                text = item.text
                if item.attrib:
                    # need to include the needed attributes
                    fmt_dict = {}
                    for key, value in item.attrib.items():
                        if key == "reference":
                            fmt_dict[value] = comp.reference
                        elif key == "value":
                            fmt_dict[value] = comp.attributes.get("Value", "<val>")
                        else:
                            fmt_dict[value] = comp.attributes[key]
                    text = text.format(**fmt_dict)

                item_tag, _ = QschTag.parse(text)
                symbol_tag.items.append(item_tag)
        else:
            if comp.rotation == 90:
                comp.rotation = 270
            elif comp.rotation == 270:
                comp.rotation = 90
            elif comp.rotation == 90 + 360:
                comp.rotation = 270 + 360
            elif comp.rotation == 270 + 360:
                comp.rotation = 90 + 360

        if symbol_tag:
            comp.attributes['symbol'] = symbol_tag

    qsch_editor = QschEditor(qsch_file, create_blank=True)
    qsch_editor.copy_from(asc_editor)
    # Save the netlist
    qsch_editor.save_netlist(qsch_file)

    print("File {} converted to {}".format(asc_file, qsch_file))


if __name__ == "__main__":
    main()
    exit(0)
