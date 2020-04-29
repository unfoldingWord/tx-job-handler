import os
import tempfile
from bs4 import BeautifulSoup
from shutil import copyfile
import yaml
import re
from typing import List

# import markdown
import markdown2

from app_settings.app_settings import AppSettings
from general_tools.file_utils import write_file, remove_tree, get_files
from converters.converter import Converter
from tx_usfm_tools.books import bookNames


class Tsv2HtmlConverter(Converter):
    """
    Class to convert TSV translationNotes into HTML pages.
    """
    # NOTE: Not all columns are passed from the preprocessor—only the used ones
    EXPECTED_TAB_COUNT = 4 # So there's one more column than this
        # (The preprocessor removes unneeded columns while fixing links.)


    def convert(self) -> bool:
        """
        Main function to convert info in TSV files into HTML files.
        """
        AppSettings.logger.debug("Tsv2HtmlConverter processing the TSV files …")

        # Find the first directory that has usfm files.
        filepaths = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)
        # convert_only_list = self.check_for_exclusive_convert()
        convert_only_list = [] # Not totally sure what the above line did

        # Process the manifest file
        self.manifest_dict = None
        for source_filepath in filepaths:
            if 'manifest.yaml' in source_filepath:
                self.process_manifest(source_filepath)
                break

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            # Simple HTML template which includes $title and $content fields
            template_html = template_file.read()

        # Convert tsv files and copy across other files
        num_successful_books = num_failed_books = 0
        for source_filepath in sorted(filepaths):
            base_name = os.path.basename(source_filepath)
            if source_filepath.endswith('.tsv'):
                if convert_only_list and (base_name not in convert_only_list):  # see if this is a file we are to convert
                    continue

                # Convert the TSV file
                self.log.info(f"Tsv2HtmlConverter converting TSV file: {base_name} …") # Logger also issues DEBUG msg
                filebase = os.path.splitext(os.path.basename(source_filepath))[0]
                # Do the actual TSV -> HTML conversion
                converted_html = self.buildSingleHtml(source_filepath)
                # AppSettings.logger.debug(f"Got converted html: {converted_html[:5000]}{' …' if len(converted_html)>5000 else ''}")
                # Now what are we doing with the converted html ???
                template_soup = BeautifulSoup(template_html, 'html.parser')
                template_soup.head.title.string = self.repo_subject
                converted_soup = BeautifulSoup(converted_html, 'html.parser')
                content_div = template_soup.find('div', id='content')
                content_div.clear()
                if converted_soup and converted_soup.body:
                    content_div.append(converted_soup.body)
                    content_div.body.unwrap()
                    num_successful_books += 1
                else:
                    content_div.append('ERROR! NOT CONVERTED!')
                    self.log.warning(f"TSV parsing or conversion error for {base_name}")
                    # AppSettings.logger.debug(f"Got converted html: {converted_html[:600]}{' …' if len(converted_html)>600 else ''}")
                    if not converted_soup:
                        AppSettings.logger.debug(f"No converted_soup")
                    elif not converted_soup.body:
                        AppSettings.logger.debug(f"No converted_soup.body")
                    # from bs4.diagnose import diagnose
                    # diagnose(converted_html)
                    num_failed_books += 1
                html_filename = filebase + '.html'
                output_filepath = os.path.join(self.output_dir, html_filename)
                #print("template_soup type is", type(template_soup)) # <class 'bs4.BeautifulSoup'>
                write_file(output_filepath, str(template_soup))
                #print("Got converted x2 html:", str(template_soup)[:500])
                self.log.info(f"Converted {os.path.basename(source_filepath)} to {os.path.basename(html_filename)}.")
            else:
                # Directly copy over files that are not TSV files
                try:
                    output_filepath = os.path.join(self.output_dir, base_name)
                    if not os.path.exists(output_filepath):
                        copyfile(source_filepath, output_filepath)
                except:
                    pass
        if num_failed_books and not num_successful_books:
            self.log.error(f"Conversion of all books failed!")
        self.log.info("Finished processing TSV files.")
        return True


    def get_truncated_string(self, original_string:str, max_length:int=100) -> str:
        """
        If a string is longer than the max_length,
            return a truncated version.
        """
        if not isinstance(original_string, str):
            original_string = str(original_string)
        if len(original_string) <= max_length:
            return original_string
        return f"{original_string[:max_length*3//4]}…{original_string[-max_length//4:]}"


    def process_manifest(self, manifest_file_path:str) -> None:
        """
        Load the yaml manifest from the given file path
            into self.manifest_dict
        """
        # AppSettings.logger.debug(f"process_manifest({manifest_file_path}) …")
        with open(manifest_file_path, 'rt') as manifest_file:
            # TODO: Check if full_load (less safe for untrusted input) is required
            #       See https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
            self.manifest_dict = yaml.safe_load(manifest_file)
        AppSettings.logger.info(f"Loaded {len(self.manifest_dict)} manifest_dict main entries: {self.manifest_dict.keys()}")
        # AppSettings.logger.debug(f"Got manifest_dict: {self.manifest_dict}")


    def get_book_names(self, filename:str) -> None:
        """
        Given a filename, search the manifest and find the book title.
            If all else fails, uses the English name of the book.

        Also gets the bookcode and English book name.

        Sets:   self.current_book_title
                self.current_book_code
                self.current_book_name
        """
        self.current_book_title = self.current_book_name = self.current_book_code = None
        if self.manifest_dict:
            for project_dict in self.manifest_dict['projects']:
                # AppSettings.logger.debug(f"get_book_names looking for '{filename}' in {project_dict} …")
                if filename in project_dict['path']:
                    self.current_book_title = project_dict['title']
                    # AppSettings.logger.debug(f"Got book_title: '{self.current_book_title}'")
                    break

        book_number_string, book_code = int(filename[-10:-8]), filename[-7:-4]
        # AppSettings.logger.debug(f"Got book_number_string: '{book_number_string}'")
        # AppSettings.logger.debug(f"Got book_code: '{book_code}'")
        self.current_book_code = book_code.lower()
        try:
            book_number = int(book_number_string)
            book_index = book_number-1 if book_number <=39 else book_number-2 # Mat-Rev are books 41-67 (not 40-66)
            english_bookname = bookNames[book_index]
        except IndexError: english_bookname = book_code
        # AppSettings.logger.debug(f"Got english_bookname: '{english_bookname}'")
        self.current_book_name = english_bookname
        if not self.current_book_title:
            self.current_book_title = self.current_book_name


    def load_tsv_file(self, tsv_filepath:str) -> None:
        """
        Load the tab separate values from the given filepath.

        Sets self.tsv_lines
        """
        MAX_ERROR_COUNT = 20
        error_count = 0
        self.tsv_lines:List[str] = []
        started = False
        with open(tsv_filepath, 'rt') as tsv_file:
            for tsv_line in tsv_file:
                tsv_line = tsv_line.rstrip('\n')
                tab_count = tsv_line.count('\t')
                if not started:
                    # AppSettings.logger.debug(f"TSV header line is '{tsv_line}")
                    # if tsv_line != 'Book	Chapter	Verse	ID	SupportReference	OrigQuote	Occurrence	GLQuote	OccurrenceNote':
                    if tsv_line != 'Book	Chapter	Verse	OrigQuote	OccurrenceNote':
                        self.log.warning(f"Unexpected TSV header line: '{tsv_line}' in {os.path.basename(tsv_filepath)}")
                        error_count += 1
                    started = True
                elif tab_count != Tsv2HtmlConverter.EXPECTED_TAB_COUNT:
                    # NOTE: This is not added to warnings because that will be done at convert time (don't want double warnings)
                    AppSettings.logger.debug(f"Unexpected line with {tab_count} tabs (expected {Tsv2HtmlConverter.EXPECTED_TAB_COUNT}): '{tsv_line}'")
                    error_count += 1
                self.tsv_lines.append(tsv_line.split('\t'))
                if error_count > MAX_ERROR_COUNT:
                    AppSettings.logger.critical("Tsv2HtmlConverter: Too many TSV count errors—aborting!")
                    break
        AppSettings.logger.info(f"Preloaded {len(self.tsv_lines):,} TSV lines from {os.path.basename(tsv_filepath)}.")


    def buildSingleHtml(self, tsv_filepath:str) -> str:
        """
        Convert TSV info for one book to HTML.

        Returns the HTML page.
        """
        # AppSettings.logger.debug(f"buildSingleHtml({tsv_filepath}) …")
        self.get_book_names(os.path.basename(tsv_filepath))
        # AppSettings.logger.debug(f"Got current_book_title: '{self.current_book_title}'")

        output_html = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8"></meta>
    <title>""" + self.current_book_title + """</title>
    <style media="all" type="text/css">
    .indent-0 {
        margin-left:0em;
        margin-bottom:0em;
        margin-top:0em;
    }
    .indent-1 {
        margin-left:0em;
        margin-bottom:0em;
        margin-top:0em;
    }
    .indent-2 {
        margin-left:1em;
        margin-bottom:0em;
        margin-top:0em;
    }
    .indent-3 {
        margin-left:2em;
        margin-bottom:0em;
        margin-top:0em;
    }
    .c-num {
        color:gray;
    }
    .v-num {
        color:gray;
    }
    .tetragrammaton {
        font-variant: small-caps;
    }
    .d {
        font-style: italic;
    }
    .footnotes {
        font-size: 0.8em;
    }
    .footnotes-hr {
        width: 90%;
    }
    </style>

</head>
<body>
<h1>""" + self.current_book_title + """</h1>
"""
        self.load_tsv_file(tsv_filepath)

        B = C = V = None # In case we get an error on the first line
        lastC = lastV = None
        for tsv_line in self.tsv_lines[1:]: # Skip the header line
            # AppSettings.logger.debug(f"Processing {tsv_line} …")
            try:
                B, C, V, OrigQuote, OccurrenceNote = tsv_line
            except ValueError:
                self.log.warning(f"Unable to convert bad TSV line (wrong number of fields) near {B} {C}:{V} = {self.get_truncated_string(tsv_line)}")
                output_html += f'<p>BAD SOURCE LINE NOT CONVERTED: {tsv_line}</p>'
                continue
            if C!=lastC: # New chapter
                output_html += f'<h2 class="section-header" id="tn-chapter-{self.current_book_code}-{C.zfill(3)}">{self.current_book_name} {C}</h2>\n'
            if V!=lastV: # Onto a new verse
                if V != 'intro': # suppress these
                    output_html += f'<h3 class="section-header" id="tn-chunk-{self.current_book_code}-{C.zfill(3)}-{V.zfill(3)}">{self.current_book_name} {C}:{V}</h3>\n'
            if OrigQuote:
                output_html += f'<p>{OrigQuote}</p>\n'
            if OccurrenceNote:
                output_html += markdown2.markdown(OccurrenceNote \
                                                    .replace('<br>','\n').replace('<br/>','\n') \
                                                    .replace('\n#','\n###')) # Increment heading levels by 2
                # for bit in OccurrenceNote.split('<br>'):
                #     if bit.startswith('# '):
                #         output_html += f'<h3>{bit[2:]}</h3>\n'
                #     elif bit.startswith('## '):
                #         output_html += f'<h4>{bit[3:]}</h4>\n'
                #     elif bit.startswith('### '):
                #         output_html += f'<h5>{bit[4:]}</h5>\n'
                #     elif bit.startswith('#### '):
                #         output_html += f'<h6>{bit[5:]}</h6>\n'
                #     elif bit.startswith('##### '):
                #         output_html += f'<h7>{bit[6:]}</h7>\n'
                #     elif bit:
                #         if bit.startswith('#'):
                #             self.log.warning(f"{B} {C}:{V} has unexpected bit: '{bit}'")
                #         output_html += f'<p>{bit}</p>\n'
            lastC, lastV = C, V

        return output_html + "</body></html>"