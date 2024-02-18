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
# Name:        asc_to_qsch.py
# Purpose:     Convert an ASC file to a QSCH schematic
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-02-2024
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import xml.etree.ElementTree as ET

from spicelib.editor.asc_editor import AscEditor
from spicelib.editor.qsch_editor import QschEditor, QschTag, QSCH_INV_ROTATION_DICT


def main():
    """Converts an ASC file to a QSCH schematic"""
    import sys
    import os.path

    if len(sys.argv) < 2:
        print("Usage: asc_to_qsch.py ASC_FILE [QSCH_FILE]")
        sys.exit(-1)

    asc_file = sys.argv[1]
    if len(sys.argv) > 2:
        qsch_file = sys.argv[2]
    else:
        qsch_file = os.path.splitext(asc_file)[0] + ".qsch"

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
        if symbol_tree is None:
            symbol_tree = symbols.get("not_found")
        name = symbol_tree.find("name").text
        offset = symbol_tree.find('offset')
        offset_x = int(offset.get('x'))
        offset_y = int(offset.get('y'))
        comp.position.X += offset_x
        comp.position.Y += offset_y
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

        comp.attributes['symbol'] = symbol_tag

    qsch_editor = QschEditor(qsch_file, create_blank=True)
    qsch_editor.copy_from(asc_editor)
    # Save the netlist
    qsch_editor.save_netlist(qsch_file)

    print("File {} converted to {}".format(asc_file, qsch_file))


if __name__ == "__main__":
    main()
    exit(0)
