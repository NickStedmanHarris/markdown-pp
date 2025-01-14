# Copyright 2015 John Reese
# Licensed under the MIT license

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import glob
import re
import yaml
from os import path

from MarkdownPP.Module import Module
from MarkdownPP.Transform import Transform


class Include(Module):
    """
    Module for recursively including the contents of other files into the
    current document using a command like `!INCLUDE "path/to/filename"`.
    Target paths can be absolute or relative to the file containing the command
    """
    #---- Frontmatter additions
    # Place to store all front matter collected throughout this module. This will be written to disk as a pickle? yaml? after module completes
    all_frontmatter = {}
    vprint = print if False else lambda *a, **k: None

    frontmatterre = re.compile(r"\A---(.*?)---\s*(.*?)\s*\Z", flags=re.DOTALL | re.MULTILINE)

    thisre = re.compile(r'!FRONTMATTER\s+this,')
    #----

    # matches !INCLUDE directives in .mdpp files
    #includere = re.compile(r"^!INCLUDE\s+(?:\"([^\"]+)\"|'([^']+)')"
    #                          r"\s*(?:,\s*(\d+))?\s*$")
    includere = re.compile(r"^!INCLUDE\s+(?:\"([^\"]+)\"|'([^']+)')\s*(?:,\s*L?E?V?E?L?\s?(\d+))?\s*$") # New regex allows us to write LEVEL before shift value for clarity
    # CONTINUE HERE> this regex is brpoken for some reason...?

    # matches title lines in Markdown files
    titlere = re.compile(r"^(:?#+.*|={3,}|-{3,})$")

    # matches unescaped formatting characters such as ` or _
    formatre = re.compile(r"[^\\]?[_*`]")

    # includes should happen before anything else
    priority = 0

    def transform(self, data):
        transforms = []

        linenum = 0
        for line in data:
            match = self.includere.search(line)
            if match:
                includedata = self.include(match)

                transform = Transform(linenum=linenum, oper="swap",
                                      data=includedata)
                transforms.append(transform)

            linenum += 1

        return transforms

    def include_file(self, filename, pwd="", shift=0):
        try:
            # File is read into memory
            with open(filename, "r", encoding = self.encoding) as f:
                data = f.readlines()
                
            # --- YAML additions
            # YAML Frontmatter is detected, parsed and stored in memory
            frontmatter = ''
            match = self.frontmatterre.match(''.join(data))
            if match:
                frontmatter, data = match.groups()         # get yaml frontmatter as string
                frontmatter = yaml.safe_load(frontmatter)   # get yaml frontmatter as dictionary from string
                if isinstance(frontmatter, list) or isinstance(frontmatter, dict):
                    self.vprint(f"[+] Frontmatter found for {path.basename(filename)}. Adding...", end='')
                    self.all_frontmatter[filename] = frontmatter
                    self.vprint('done')
                
                # Sneakily substitute "!FRONTMATTER this," to "!FRONTMATTER id.id,"
                this_id = f"id.{frontmatter.get('id', 'UNDEF')}"
                data = self.thisre.sub(f"!FRONTMATTER {this_id},", data)

                data = [line+'\n' for line in data.split('\n')]
            else:
                self.vprint('NO MATCH')
            # ---

            # line by line, apply shift and recursively include file data
            linenum = 0
            includednum = 0

            for line in data:
                match = self.includere.search(line)
                if match:
                    dirname = path.dirname(filename)
                    data[linenum:linenum+1] = self.include(match, dirname)
                    includednum = linenum
                    # Update line so that we won't miss a shift if
                    # heading is on the 1st line.
                    line = data[linenum]

                if shift:

                    titlematch = self.titlere.search(line)
                    if titlematch:
                        to_del = []
                        for _ in range(shift):
                            # Skip underlines with empty above text
                            # or underlines that are the first line of an
                            # included file
                            prevtxt = re.sub(self.formatre, '',
                                             data[linenum - 1]).strip()
                            isunderlined = prevtxt and linenum > includednum
                            if data[linenum][0] == '#':
                                data[linenum] = "#" + data[linenum]
                            elif data[linenum][0] == '=' and isunderlined:
                                data[linenum] = data[linenum].replace("=", '-')
                            elif data[linenum][0] == '-' and isunderlined:
                                data[linenum] = '### ' + data[linenum - 1]
                                to_del.append(linenum - 1)
                        for l in to_del:
                            del data[l]

                linenum += 1

            return data

        except (IOError, OSError) as exc:
            print(exc)

        return []

    def include(self, match, pwd=""): ### NOTE: Transform calls this function on a list of mdpp files scraped with the regex. Yaml write here.
        # file name is caught in group 1 if it's written with double quotes,
        # or group 2 if written with single quotes
        fileglob = match.group(1) or match.group(2)

        shift = int(match.group(3) or 0)

        result = []
        if pwd != "":
            fileglob = path.join(pwd, fileglob)

        files = sorted(glob.glob(fileglob))
        if len(files) > 0:
            for filename in files:
                result += self.include_file(filename, pwd, shift)
        else:
            result.append("")

        if self.all_frontmatter:
            self.vprint('\n[+] frontmatter was collected. Writing to output file...', end='')
            with open('frontmatter.yaml', 'w') as fp:
                fp.write(yaml.dump(self.all_frontmatter))
                self.vprint('done')
        
        return result
