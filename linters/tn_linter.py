import os
import re
import tempfile

from global_settings.global_settings import GlobalSettings
from door43_tools.bible_books import BOOK_NUMBERS
from general_tools import file_utils, url_utils
from tx_usfm_tools.usfm_verses import verses
from linters.markdown_linter import MarkdownLinter
from linters.linter import Linter


class TnLinter(MarkdownLinter):

    # match links of form '](link)'
    link_marker_re = re.compile(r'\]\(([^\n()]+)\)')
    expected_tab_count = 8

    def __init__(self, single_file=None, *args, **kwargs):
        super(TnLinter, self).__init__(*args, **kwargs)

        self.single_file = single_file
        GlobalSettings.logger.debug(f"Convert single '{self.single_file}'")
        self.single_dir = None
        if self.single_file:
            parts = os.path.splitext(self.single_file)
            self.single_dir = self.get_dir_for_book(parts[0])
            GlobalSettings.logger.debug(f"Single source dir '{self.single_dir}'")


    def lint(self):
        """
        Checks for issues with translationNotes

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.md)
        :return boolean:
        """
        self.source_dir = os.path.abspath(self.source_dir)
        source_dir = self.source_dir if not self.single_dir else os.path.join(self.source_dir, self.single_dir)
        for root, _dirs, files in os.walk(source_dir):
            for f in files:
                file_path = os.path.join(root, f)
                parts = os.path.splitext(f)
                if parts[1] == '.md':
                    contents = file_utils.read_file(file_path)
                    self.find_invalid_links(root, f, contents)

        for dir in BOOK_NUMBERS:
            found_files = False
            if self.single_dir and (dir != self.single_dir):
                continue
            GlobalSettings.logger.debug(f"Processing folder {dir}")
            file_path = os.path.join(self.source_dir, dir)
            for root, _dirs, files in os.walk(file_path):
                if root == file_path:
                    continue  # skip book folder

                if files:
                    found_files = True
                    break

            if not found_files \
            and 'OBS' not in self.repo_subject \
            and len(self.rc.projects) != 1: # Many repos are intentionally just one book
                msg = f"Missing tN book: '{dir}'"
                GlobalSettings.logger.debug(msg)
                self.log.warnings.append(msg)

        results = super(TnLinter, self).lint()  # Runs checks on Markdown, using the markdown linter
        if not results:
            GlobalSettings.logger.debug(f"Error running MD linter on {self.s3_results_key}")
        return results


    def find_invalid_links(self, folder, f, contents):
        for link_match in TnLinter.link_marker_re.finditer(contents):
            link = link_match.group(1)
            if link:
                if link[:4] == 'http':
                    continue
                if link.find('.md') < 0:
                    continue

                file_path = os.path.join(folder, link)
                file_path_abs = os.path.abspath(file_path)
                exists = os.path.exists(file_path_abs)
                if not exists:
                    a = self.get_file_link(f, folder)
                    msg = f"{a}: contains invalid link: ({link})"
                    self.log.warnings.append(msg)
                    GlobalSettings.logger.debug(msg)

    def get_file_link(self, f, folder):
        parts = folder.split(self.source_dir)
        sub_path = self.source_dir  # default
        if len(parts) == 2:
            sub_path = parts[1][1:]
        url = f"https://git.door43.org/{self.repo_owner}/{self.repo_name}/src/master/{sub_path}/{f}"
        a = f'<a href="{url}">{sub_path}/{f}</a>'
        return a
# end of TnLinter class



class TnTsvLinter(Linter):

    # match links of form '](link)'
    link_marker_re = re.compile(r'\]\(([^\n()]+)\)')
    expected_tab_count = 8

    def __init__(self, *args, **kwargs):
        self.loaded_file_path = None
        self.loaded_file_contents = None
        self.preload_dir = tempfile.mkdtemp(prefix='tX_tN_linter_preload_')
        super(TnTsvLinter, self).__init__(*args, **kwargs)


    def lint(self):
        """
        Checks for issues with translationNotes

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.tsv)
        :return boolean:
        """
        self.source_dir = os.path.abspath(self.source_dir)
        source_dir = self.source_dir
        for root, _dirs, files in os.walk(source_dir):
            for f in files:
                file_path = os.path.join(root, f)
                if os.path.splitext(f)[1] == '.tsv':
                    contents = file_utils.read_file(file_path)
                    self.find_invalid_links(root, f, contents)

        file_list = os.listdir(source_dir)
        for dir in BOOK_NUMBERS:
            found_file = False
            for file_name in file_list:
                if file_name.endswith('.tsv') and dir.upper() in file_name:
                    found_file = True
                    break
            if not found_file:
                msg = f"Missing tN tsv book: '{dir}'"
                self.log.warnings.append(msg)
                GlobalSettings.logger.debug(msg)

        # See if manifest has relationships back to original language versions
        need_to_check_quotes = False
        rels = self.rc.resource.relation
        if isinstance(rels, list):
            for rel in rels:
                if 'hbo/uhb' in rel:
                    url = f"https://cdn.door43.org/{rel.replace('?v=', '/v')}/uhb.zip"
                    self.preload_original_text_archive('uhb', url)
                    need_to_check_quotes = True
                if 'el-x-koine/ugnt' in rel:
                    url = f"https://cdn.door43.org/{rel.replace('?v=', '/v')}/ugnt.zip"
                    self.preload_original_text_archive('ugnt', url)
                    need_to_check_quotes = True

        # Now check tabs and C:V numbers
        for filename in sorted(file_list):
            if not filename.endswith('.tsv'): continue # Skip other files
            GlobalSettings.logger.info(f"Linting {filename} …")
            tsv_filepath = os.path.join(source_dir, filename)
            started = False
            expectedB = filename[-7:-4]
            lastC = lastV = C = V = '0'
            with open(tsv_filepath, 'rt') as tsv_file:
                for tsv_line in tsv_file:
                    tsv_line = tsv_line.rstrip('\n')
                    tab_count = tsv_line.count('\t')
                    if not started:
                        # GlobalSettings.logger.debug(f"TSV header line is '{tsv_line}'")
                        if tsv_line != 'Book	Chapter	Verse	ID	SupportReference	OrigQuote	Occurrence	GLQuote	OccurrenceNote':
                            self.log.warnings.append(f"Unexpected TSV header line: '{tsv_line}' in {filename}")
                        started = True
                    elif tab_count != TnTsvLinter.expected_tab_count:
                        self.log.warnings.append(f"Bad {expectedB} line near {C}:{V} with {tab_count} tabs (expected {TnTsvLinter.expected_tab_count})")
                        B = C = V = _ID = _SupportReference = OrigQuote = _Occurrence = _GLQuote = OccurrenceNote = None
                    else:
                        B, C, V, _ID, _SupportReference, OrigQuote, _Occurrence, _GLQuote, OccurrenceNote = tsv_line.split('\t')
                        if B != expectedB:
                            self.log.warnings.append(f"Unexpected {B} line in {filename}")
                        if not C:
                            self.log.warnings.append(f"Missing chapter number after {lastC}:{lastV} in {filename}")
                        elif not C.isdigit() and C not in ('front','back'):
                            self.log.warnings.append(f"Bad '{C}' chapter number near verse {V} in {filename}")
                        elif C.isdigit() and lastC.isdigit():
                            lastCint, Cint = int(lastC), int(C)
                            if Cint < lastCint:
                                self.log.warnings.append(f"Decrementing '{C}' chapter number after {lastC} in {filename}")
                            elif Cint > lastCint+1:
                                self.log.warnings.append(f"Missing chapter number {lastCint+1} after {lastC} in {filename}")
                        if C == lastC: # still in the same chapter
                            if not V.isdigit():
                                self.log.warnings.append(f"Bad '{V}' verse number in chapter {C} in {filename}")
                            elif lastV.isdigit():
                                lastVint, Vint = int(lastV), int(V)
                                if Vint < lastVint:
                                    self.log.warnings.append(f"Decrementing '{V}' verse number after {lastV} in chapter {C} in {filename}")
                                # NOTE: Disabled because missing verse notes are expected
                                # elif Vint > lastVint+1:
                                    # self.log.warnings.append(f"Missing verse number {lastVint+1} after {lastV} in chapter {C} in {filename}")
                        else: # just started a new chapter
                            if not V.isdigit() and V != 'intro':
                                self.log.warnings.append(f"Bad '{V}' verse number in start of chapter {C} in {filename}")
                        if OrigQuote and need_to_check_quotes:
                            self.check_original_language_quotes(B,C,V,OrigQuote)
                        if OccurrenceNote:
                            left_count, right_count = OccurrenceNote.count('['), OccurrenceNote.count(']')
                            if left_count != right_count:
                                self.log.warnings.append(f"Unmatched square brackets at {B} {C}:{V} in '{OccurrenceNote}'")
                            self.check_markdown(OccurrenceNote, f"{B} {C}:{V}")
                        lastC, lastV = C, V
                        if lastC == 'front': lastC = '0'
                        elif lastC == 'back': lastC = '999'

        file_utils.remove_tree(self.preload_dir)
        return True
    # end of TnTsvLinter.lint()


    def check_markdown(self, markdown_string, reference):
        """
        Checks the header progressions in the markdown string
        """
        header_level = 0
        for bit in markdown_string.split('<br>'):
            if bit.startswith('# '):
                header_level = 1
            elif bit.startswith('## '):
                if header_level < 1:
                    self.log.warnings.append(f"Markdown header jumped directly to level 2 at {reference}")
                header_level = 2
            elif bit.startswith('### '):
                if header_level < 2:
                    self.log.warnings.append(f"Markdown header jumped directly to level 3 at {reference}")
                header_level = 3
            elif bit.startswith('#### '):
                if header_level < 3:
                    self.log.warnings.append(f"Markdown header jumped directly to level 4 at {reference}")
                header_level = 4
            elif bit.startswith('##### '):
                if header_level < 4:
                    self.log.warnings.append(f"Markdown header jumped directly to level 5 at {reference}")
                header_level = 5
            elif bit.startswith('#'):
                self.log.warning(f"Badly formatted markdown header at {reference}")
    # end of TnTsvLinter.check_markdown function


    def preload_original_text_archive(self, name, zip_url):
        """
        Fetch and unpack the Hebrew/Greek zip file.
        """
        GlobalSettings.logger.info(f"preload_original_text_archive({name}, {zip_url})…")
        zip_path = os.path.join(self.preload_dir, f'{name}.zip')
        try:
            url_utils.download_file(zip_url, zip_path)
            file_utils.unzip(zip_path, self.preload_dir)
            file_utils.remove(zip_path)
        except Exception as e:
            GlobalSettings.logger.error(f"Unable to download {zip_url}: {e}")
        # GlobalSettings.logger.debug(f"Got {name} files:", os.listdir(self.preload_dir))
    # end of TnTsvLinter.preload_original_text_archive function


    def check_original_language_quotes(self, B,C,V, quoteField):
        """
        Check that the quoted portions can indeed be found in the original language versions.
        """
        # if B in ('RUT','EZR'): return # Skip checking of these books TEMP XXXXXXXXXXXXXXXXXXXXXXXXXX
        # GlobalSettings.logger.debug(f"check_original_language_quotes({B},{C},{V}, {quoteField})…")
        verse_text = self.get_passage(B,C,V)

        if '...' in quoteField and '…' in quoteField:
            GlobalSettings.logger.debug(f"Mixed ellipses in {B} {C}:{V} '{quoteField}'")
            self.log.warnings.append(f"Mixed ellipse characters in {B} {C}:{V} '{quoteField}'")
            return # Don't check further

        if '...' in quoteField:
            quoteBits = quoteField.split(' ... ')
        elif '…' in quoteField:
            quoteBits = quoteField.split(' … ')
        else:
            quoteBits = None

        if quoteBits:
            if len(quoteBits) >= 2:
                for index in range(len(quoteBits)):
                    if quoteBits[index] not in verse_text:
                        description = 'middle'
                        if index == 0: description = 'beginning'
                        elif index == len(quoteBits)-1: description = 'end'
                        GlobalSettings.logger.debug(f"Unable to find {B} {C}:{V} '{quoteBits[index]}' ({description}/{index}) in '{verse_text}'")
                        self.log.warnings.append(f"Unable to find {B} {C}:{V} {description} of '{quoteField}' in '{verse_text}'")
            else: # < 2
                self.log.warnings.append(f"Invalid quote field with ellipsis at {B} {C}:{V} '{quoteField}'")
        elif quoteField not in verse_text:
            GlobalSettings.logger.debug(f"Unable to find {B} {C}:{V} '{quoteField}' in '{verse_text}'")
            self.log.warnings.append(f"Unable to find {B} {C}:{V} '{quoteField}' in '{verse_text}'")
    # end of TnTsvLinter.check_original_language_quotes function


    def get_passage(self, B, C,V):
        """
        Get the information for the given verse out of the appropriate book file.

        Also removes milestones and extra word (\\w) information
        """
        # GlobalSettings.logger.debug(f"get_passage({B}, {C},{V})…")
        book_number = verses[B]["usfm_number"]
        # NOTE: Lazy way to determine which testament the book is in
        book_path = os.path.join(self.preload_dir, f'{book_number}-{B}.usfm')
        if not os.path.isfile(book_path):
            book_path = os.path.join(self.preload_dir, 'hbo_uhb/', f'{book_number}-{B}.usfm')
            if not os.path.isfile(book_path):
                book_path = os.path.join(self.preload_dir, 'el-x-koine_ugnt/', f'{book_number}-{B}.usfm')
        if self.loaded_file_path != book_path:
            # It's not cached already
            GlobalSettings.logger.info(f"Reading {book_path}…")
            with open(book_path, 'rt') as book_file:
                self.loaded_file_contents = book_file.read()
            self.loaded_file_path = book_path
            # Do some initial cleaning and convert to lines
            self.loaded_file_contents = self.loaded_file_contents \
                                            .replace('\\zaln-e\\*','') \
                                            .replace('\\k-e\\*', '') \
                                            .split('\n')
        # print("loaded_book_contents", self.loaded_file_contents)
        found_chapter = found_verse = False
        verseText = ''
        for book_line in self.loaded_file_contents:
            if not found_chapter and book_line == f'\\c {C}':
                found_chapter = True
                continue
            if found_chapter and not found_verse and book_line.startswith(f'\\v {V}'):
                found_verse = True
                continue
            if found_verse:
                if book_line.startswith('\\v '):
                    break
                ix = book_line.find('\\k-s ')
                if ix != -1:
                    book_line = book_line[:ix] # Remove k-s field right up to end of line
                verseText += ' ' + book_line
        verseText = verseText.replace('  ', ' ').strip()
        # print(f"Got verse text1: '{verseText}'")
        # Remove \w fields (just leaving the word)
        ixW = verseText.find('\\w ')
        while ixW != -1:
            ixEnd = verseText.find('\\w*', ixW)
            # assert ixEnd != -1 # Fail if closing marker is missing from the line -- fails on UGNT ROM 8:28
            if ixEnd != -1:
                field = verseText[ixW+3:ixEnd]
                # GlobalSettings.logger.debug(f"Cleaning \\w field: {field!r} from '{line}'")
                bits = field.split('|')
                adjusted_field = bits[0]
                # GlobalSettings.logger.debug(f"Adjusted field to: {adjusted_field!r}")
                verseText = verseText[:ixW] + adjusted_field + verseText[ixEnd+3:]
                # GlobalSettings.logger.debug(f"Adjusted line to: '{adjusted_line}'")
            else:
                GlobalSettings.logger.error(f"Missing \\w* in {B} {C}:{V} verseText: '{verseText}'")
                # self.warnings.append(f"{B} {C}:{V} - Missing \\w* closure")
                verseText = verseText.replace('\\w ','') # Attempt to continue
            ixW = verseText.find('\\w ', ixW+1) # Might be another one
        # print(f"Got verse text2: '{verseText}'")
        return verseText.replace('  ', ' ')
    # end of TnTsvLinter.get_passage function


    def find_invalid_links(self, folder, f, contents):
        # GlobalSettings.logger.debug(f"TnTsvLinter.find_invalid_links( {folder}, {f}, {contents} ) …")
        for link_match in TnLinter.link_marker_re.finditer(contents):
            link = link_match.group(1)
            if link:
                if link[:4] == 'http':
                    continue
                if link.find('.tsv') < 0:
                    continue

                file_path = os.path.join(folder, link)
                file_path_abs = os.path.abspath(file_path)
                exists = os.path.exists(file_path_abs)
                if not exists:
                    a = self.get_file_link(f, folder)
                    msg = f"{a}: contains invalid link: ({link})"
                    self.log.warnings.append(msg)
                    GlobalSettings.logger.debug(msg)
    # end of TnTsvLinter.find_invalid_links function

    def get_file_link(self, f, folder):
        parts = folder.split(self.source_dir)
        sub_path = self.source_dir  # default
        if len(parts) == 2:
            sub_path = parts[1][1:]
        url = f"https://git.door43.org/{self.repo_owner}/{self.repo_name}/src/master/{sub_path}/{f}"
        a = f'<a href="{url}">{sub_path}/{f}</a>'
        return a
    # end of TnTsvLinter.get_file_link function
# end of TnTsvLinter class
