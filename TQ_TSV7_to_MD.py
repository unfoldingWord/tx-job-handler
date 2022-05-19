#!/usr/bin/env python3
#
# TQ_TSV7_to_MD.py
#
# Copyright (c) 2020-2021 unfoldingWord
# http://creativecommons.org/licenses/MIT/
# See LICENSE file for details.
#
# Contributors:
#   Robert Hunt <Robert.Hunt@unfoldingword.org>
#
# Written Nov 2020 by RJH
#   Last modified: 2021-05-05 by RJH
#
"""
Quick script to copy TQ from 7-column TSV files
    and put back into the older markdown format (for compatibility reasons)
"""
from typing import List, Tuple, Optional
import os
import sys
import shutil
from pathlib import Path
import random
import re
import logging
from door43_tools.bible_books import BOOK_NUMBERS

tsv_path = None
md_path = None

def get_TSV_fields(input_folderpath:Path, BBB:str) -> Tuple[str,str,str]:
    """
    Generator to read the TQ 7-column TSV file for a given book (BBB)
        and return the needed fields.

    Skips the heading row.
    Checks that unused fields are actually unused.

    Returns a 3-tuple with:
        reference, question, response
    """
    print(f"    Loading TQ {BBB} links from 7-column TSV…")
    input_filepath = os.path.join(input_folderpath, f'tq_{BBB}.tsv')
    with open(input_filepath, 'rt') as input_TSV_file:
        for line_number, line in enumerate(input_TSV_file, start=1):
            line = line.rstrip('\n\r')
            # print(f"{line_number:3}/ {line}")
            if line_number == 1:
                assert line == 'Reference\tID\tTags\tQuote\tOccurrence\tQuestion\tResponse'
            else:
                reference, rowID, tags, quote, occurrence, question, response = line.split('\t')
                assert reference; assert rowID; assert question; assert response
                assert not tags; assert not quote; assert not occurrence
                yield reference, question, response
# end of get_TSV_fields function


current_BCV = None
markdown_text = ''
def handle_output(output_folderpath:Path, BBB:str, fields:Optional[Tuple[str,str,str]]) -> int:
    """
    Function to write the TQ markdown files.

    Needs to be called one extra time with fields = None
        to write the last entry.

    Returns the number of markdown files that were written in the call.
    """
    global current_BCV, markdown_text
    # print(f"handle_output({output_folderpath}, {BBB}, {fields})…")

    num_files_written = 0

    if fields is None:
        verse_ranges = [['1', '1']]
    else: # have fields
        reference, question, response = fields
        C, V = reference.split(':')
        # if C == '18' and V =='3': halt

        verse_ranges = V.split(',')
        for idx, verse_range in enumerate(verse_ranges):
            verse_range = verse_range.strip()
            if '-' in verse_range:
                verse_ranges[idx] = verse_range.split('-') # it's a real range
            else:
                verse_ranges[idx] = [verse_range, verse_range]

    for verse_range in verse_ranges:
        for intV in range(int(verse_range[0]), int(verse_range[1])+1):
            V = str(intV)
            if (fields is None # We need to write the last file
            or (markdown_text and (BBB,C,V) != current_BCV)): # need to write the previous verse file
                assert BBB == current_BCV[0]
                prevC, prevV = current_BCV[1:]
                this_folderpath = os.path.join(output_folderpath, f'{BBB.lower()}/{prevC.zfill(2)}/')
                if not os.path.exists(this_folderpath): os.makedirs(this_folderpath)
                output_filepath = os.path.join(this_folderpath, f'{prevV.zfill(2)}.md')
                try:
                    with open(output_filepath, 'rt') as previous_markdown_file:
                        previous_markdown_text = previous_markdown_file.read()
                except FileNotFoundError: previous_markdown_text = ''
                if previous_markdown_text:
                    # markdown_text = f"{markdown_text}\n{previous_markdown_text}"
                    markdown_text = f"{previous_markdown_text}\n{markdown_text}"
                with open(output_filepath, 'wt') as output_markdown_file:
                    output_markdown_file.write(markdown_text)
                # print(f"  Wrote {len(markdown_text):,} bytes to {str(output_filepath).replace(str(output_folderpath), '')}")
                num_files_written += 1
                markdown_text = ''

            if fields is not None:
                current_BCV = BBB, C, V
                if markdown_text: markdown_text += '\n' # Blank line between questions
                markdown_text += f'# {question}\n\n{response}\n' # will be written on the next call

    return num_files_written
# end of handle_output function


def convert_tsv_tq_to_md_tq(tsv, md):
    """
    """
    global tsv_path, md_path
    tsv_path = tsv
    md_path = md
    print("TQ_TSV7_to_MD.py")
    print(f"  Source folderpath is {tsv_path}/")
    print(f"  Output folderpath is {md_path}/")
    total_files_read = total_questions = total_files_written = 0
    for BBB in BOOK_NUMBERS:
        if BOOK_NUMBERS[BBB] < '01' or BOOK_NUMBERS[BBB] > '67':
            continue
        # Remove the folder first in case any questions have been deleted
        try: shutil.rmtree(os.path.join(md_path, f'{BBB.lower()}/'))
        except FileNotFoundError: pass # wasn't there
        for input_fields in get_TSV_fields(tsv_path,BBB):
            total_files_written += handle_output(md_path,BBB,input_fields)
            total_questions += 1
        total_files_read += 1
        total_files_written += handle_output(md_path,BBB,None) # To write last file
    print(f"  {total_questions:,} total questions and answers read from {total_files_read} TSV files")
    print(f"  {total_files_written:,} total verse files written to {md_path}/")
# end of main function

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python TQ_TSV7_to_MD.py <path to TSV TQ dir> <path to MD TQ dir>")
        sys.exit(1)
    if not os.path.exists(sys.argv[1]):
        print(f"TSV TQ path does not exist: {sys.argv[1]}")
        sys.exit(1)
    if not os.path.exists(sys.argv[2]):
        print(f"MD TQ path does not exist: {sys.argv[2]}")
        sys.exit(1)
    convert_tsv_tq_to_md_tq(sys.argv[1], sys.argv[2])
