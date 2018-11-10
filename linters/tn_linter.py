import os
import re
from global_settings.global_settings import GlobalSettings
from door43_tools.bible_books import BOOK_NUMBERS
from general_tools import file_utils
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
        for root, dirs, files in os.walk(source_dir):
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
            for root, dirs, files in os.walk(file_path):
                if root == file_path:
                    continue  # skip book folder

                if len(files) > 0:
                    found_files = True
                    break

            if not found_files:
                msg = f"missing book: '{dir}'"
                self.log.warnings.append(msg)
                GlobalSettings.logger.debug(msg)

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


class TnTsvLinter(Linter):

    # match links of form '](link)'
    link_marker_re = re.compile(r'\]\(([^\n()]+)\)')
    expected_tab_count = 8

    def __init__(self, *args, **kwargs):
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
        for root, dirs, files in os.walk(source_dir):
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
                msg = f"Missing book: '{dir}'"
                self.log.warnings.append(msg)
                GlobalSettings.logger.debug(msg)

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
                    else:
                        B, C, V, ID, SupportReference, OrigQuote, Occurrence, GLQuote, OccurrenceNote = tsv_line.split('\t')
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
                        if OccurrenceNote:
                            left_count, right_count = OccurrenceNote.count('['), OccurrenceNote.count(']')
                            if left_count != right_count:
                                self.log.warnings.append(f"Unmatched square brackets at {B} {C}:{V} in '{OccurrenceNote}'")
                        lastC, lastV = C, V
                        if lastC == 'front': lastC = '0'
                        elif lastC == 'back': lastC = '999'

        return True

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

    def get_file_link(self, f, folder):
        parts = folder.split(self.source_dir)
        sub_path = self.source_dir  # default
        if len(parts) == 2:
            sub_path = parts[1][1:]
        url = f"https://git.door43.org/{self.repo_owner}/{self.repo_name}/src/master/{sub_path}/{f}"
        a = f'<a href="{url}">{sub_path}/{f}</a>'
        return a
