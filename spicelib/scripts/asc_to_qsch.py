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
import os
import logging
import xml.etree.ElementTree as ET

from spicelib.editor.asy_reader import AsyReader
from spicelib.editor.asc_editor import AscEditor
from spicelib.editor.qsch_editor import QschEditor
from spicelib.utils.file_search import find_file_in_directory

_logger = logging.getLogger("spicelib.AscToQsch")


def main():
    """Converts an ASC file to a QSCH schematic"""
    import os.path
    from optparse import OptionParser

    opts = OptionParser(
        usage="usage: %prog [options] ASC_FILE [QSCH_FILE]",
        version="%prog 0.1")

    opts.add_option('-a', "--add", action="append", type="string", dest="path",
                    help="Add a path for searching for symbols")

    (options, args) = opts.parse_args()

    if len(args) < 1:
        opts.print_help()
        exit(-1)

    asc_file = args[0]
    if len(args) > 1:
        qsch_file = args[1]
    else:
        qsch_file = os.path.splitext(asc_file)[0] + ".qsch"

    search_paths = [] if options.path is None else options.path

    print(f"Using {qsch_file} as output file")
    convert_asc_to_qsch(asc_file, qsch_file, search_paths)


def convert_asc_to_qsch(asc_file, qsch_file, search_paths=[]):
    """Converts an ASC file to a QSCH schematic"""
    symbol_stock = {}
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
    # symbol_stock = {sym.find('LT_name').text: sym for sym in root.findall('component_symbols/symbol')}
    # The symbol_stock has native QSpice symbols and information on how to replace the LTSpice symbols by
    # QSpice ones. For now this is not operational
    for comp in asc_editor.components.values():
        symbol_tag = symbol_stock.get(comp.symbol, None)
        if symbol_tag is None:
            # Will try to get it from the sym folder
            print(f"Searching for symbol {comp.symbol}...")
            # TODO: this should use the default locations from AscEditor, and use search_file_in_containers, just like AscEditor does.
            for sym_root in search_paths + [
                # os.path.curdir,  # The current script directory
                os.path.split(asc_file)[0],  # The directory where the script is located
                os.path.expanduser("~/AppData/Local/LTspice/lib/sym"),
                os.path.expanduser("~/Documents/LtspiceXVII/lib/sym"),
                # os.path.expanduser(r"~\AppData\Local\Programs\ADI\LTspice\lib.zip"), # TODO: implement this
            ]:
                print(f"   {os.path.abspath(sym_root)}")
                if not os.path.exists(sym_root):  # Skipping invalid paths
                    continue
                if sym_root.endswith('.zip'):  # TODO: test if it is a file
                    pass
                    # Using an IO buffer to pass the file to the AsyEditor
                else:
                    symbol_asc_file = find_file_in_directory(sym_root, comp.symbol + '.asy')
                    if symbol_asc_file is not None:
                        print(f"Found {symbol_asc_file}")
                        symbol_asc = AsyReader(symbol_asc_file)
                        value = comp.attributes.get('Value', '<val>')
                        symbol_tag = symbol_asc.to_qsch(comp.reference, value)
                        symbol_stock[comp.symbol] = symbol_tag
                        break

        # if symbol_tree:
        #     name = symbol_tree.find("name").text
        #     offset = symbol_tree.find('LT_origin')
        #     offset_x = int(offset.get('x'))
        #     offset_y = int(offset.get('y'))
        #
        #     if comp.rotation == ERotation.R0:
        #         comp.position.X += offset_x
        #         comp.position.Y += offset_y
        #     elif comp.rotation == ERotation.R90:
        #         comp.position.X += offset_y
        #         comp.position.Y -= offset_x
        #     elif comp.rotation == ERotation.R180:
        #         comp.position.X -= offset_x
        #         comp.position.Y -= offset_y
        #     elif comp.rotation == ERotation.R270:
        #         comp.position.X -= offset_y
        #         comp.position.Y += offset_x
        #     elif comp.rotation == ERotation.M0:
        #         comp.position.X += offset_x
        #         comp.position.Y -= offset_y
        #     elif comp.rotation == ERotation.M90:
        #         comp.position.X -= offset_y
        #         comp.position.Y -= offset_x
        #     elif comp.rotation == ERotation.M180:
        #         comp.position.X -= offset_x
        #         comp.position.Y += offset_y
        #     elif comp.rotation == ERotation.M270:
        #         comp.position.X += offset_y
        #         comp.position.Y += offset_x
        #     rotation = symbol_tree.find('rotation').text
        #     if rotation == 'R0':
        #         pass  # basically do nothing
        #     elif rotation == 'R90':
        #         comp.rotation = comp.rotation + ERotation.R90
        #     elif rotation == 'R180':
        #         comp.rotation = comp.rotation + ERotation.R180
        #     elif rotation == 'R270':
        #         comp.rotation = comp.rotation + ERotation.R270
        #     elif rotation == 'M0':
        #         comp.rotation = comp.rotation.mirror_x_axis()
        #     elif rotation == 'M90':
        #         comp.rotation = comp.rotation
        #     elif rotation == 'M180':
        #         comp.rotation = comp.rotation.M180
        #     elif rotation == 'M270':
        #         comp.rotation = comp.rotation
        #
        #     # typ = symbol_tree.find("type").text
        #     # description = symbol_tree.find("description").text
        #
        #     symbol_tag = QschTag("symbol", name)
        #     # symbol_tag.items.append(QschTag("type", typ))
        #     # symbol_tag.items.append(QschTag("description:", description))
        #     for item in symbol_tree.findall('items/item'):
        #         text = item.text
        #         if item.attrib:
        #             # need to include the needed attributes
        #             fmt_dict = {}
        #             for key, value in item.attrib.items():
        #                 if key == "reference":
        #                     fmt_dict[value] = comp.reference
        #                 elif key == "value":
        #                     fmt_dict[value] = comp.attributes.get("Value", "<val>")
        #                 else:
        #                     fmt_dict[value] = comp.attributes[key]
        #             text = text.format(**fmt_dict)
        #
        #         item_tag, _ = QschTag.parse(text)
        #         symbol_tag.items.append(item_tag)
        # else:
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
