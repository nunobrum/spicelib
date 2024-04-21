readme_update
=============

This is a script to update README.md files with real code sources.

It reads a .md documentation file at and replaces the code blocks with the actual code from source files.
The source files are specified with a special comment in the documentation file placed right after the code block.

Below is an example of a code block in a markdown file :

    .. code-block:: text

        ```python
            # this will be replaced with the actual code from path/to/source/file.py
        ```
        -- in path/to/source/file.py

The script will replace the code block with the actual code from the file specified in the comment.

If only a part of the code is to be included, the user can add a title to the code block as follows :

    .. code-block:: text

        ```python
            # this will be replaced with the actual code from path/to/source/file.py located between the comments below
            # Start of Code block Title
            ...
            # End of Code block Title
        ```
        -- in path/to/source/file.py [Code Block Title]

and the script will only include the code between the following comments:

# Start of Code block Title

# End of Code block Title


The script will create a backup of the original file before updating it. The backup file will have the same name as the
original file with the extension .bak.

Usage
=====

The readme_update.exe can be used directly from a command line if the Python's Scripts folder is included in the PATH
environment variable. If not, the full path to the executable must be provided.

    .. code-block:: bash

        readme_update.exe <path_to_md_file>
