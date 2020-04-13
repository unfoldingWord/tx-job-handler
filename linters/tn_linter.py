from typing import Optional
import os
import re

from rq_settings import prefix, debug_mode_flag
from app_settings.app_settings import AppSettings
from door43_tools.bible_books import BOOK_NUMBERS
from general_tools import file_utils
from linters.markdown_linter import MarkdownLinter
from linters.linter import Linter
from linters.py_markdown_linter.lint import MarkdownLinter as PyMarkdownLinter
from linters.py_markdown_linter.config import LintConfig


class TnLinter(MarkdownLinter):

    # match links of form '](link)'
    link_marker_re = re.compile(r'\]\(([^\n()]+)\)')

    def __init__(self, single_file:Optional[str]=None, *args, **kwargs) -> None:
        super(TnLinter, self).__init__(*args, **kwargs)

        self.single_file = single_file
        AppSettings.logger.debug(f"Convert single '{self.single_file}'")
        self.single_dir = None
        if self.single_file:
            parts = os.path.splitext(self.single_file)
            self.single_dir = self.get_dir_for_book(parts[0])
            AppSettings.logger.debug(f"Single source dir '{self.single_dir}'")


    def lint(self) -> bool:
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
            AppSettings.logger.debug(f"Processing folder {dir}")
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
                self.log.warning(f"Missing tN book: '{dir}'")

        results = super(TnLinter, self).lint()  # Runs checks on Markdown, using the markdown linter
        if not results:
            AppSettings.logger.debug(f"Error running MD linter on {self.repo_subject}")
        return results


    def find_invalid_links(self, folder:str, f:str, contents:str) -> None:
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
                    self.log.warning(f"{a}: contains invalid link: ({link})")

    def get_file_link(self, f:str, folder:str):
        parts = folder.split(self.source_dir)
        sub_path = self.source_dir  # default
        if len(parts) == 2:
            sub_path = parts[1][1:]
        self.repo_owner = self.repo_name = '' # WE DON'T KNOW THIS STUFF
        url = f"https://git.door43.org/{self.repo_owner}/{self.repo_name}/src/master/{sub_path}/{f}"
        a = f'<a href="{url}">{sub_path}/{f}</a>'
        return a
# end of TnLinter class



class TnTsvLinter(Linter):

    # match links of form '](link)'
    link_marker_re = re.compile(r'\]\(([^\n()]+)\)')
    EXPECTED_TAB_COUNT = 4 # So there's one more column than this
        # NOTE: The preprocessor removes unneeded columns while fixing links


    # def __init__(self, *args, **kwargs) -> None:
    #     super(TnTsvLinter, self).__init__(*args, **kwargs)


    def lint(self) -> bool:
        """
        Checks for issues with translationNotes

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.tsv)
        :return boolean:
        """
        lint_config = LintConfig()
        for rule_id in ('MD009', 'MD010', 'MD013'): # Ignore
            lint_config.disable_rule_by_id(rule_id)
        py_markdown_linter = PyMarkdownLinter(lint_config)

        self.source_dir = os.path.abspath(self.source_dir)
        source_dir = self.source_dir
        for root, _dirs, files in os.walk(source_dir):
            for f in files:
                file_path = os.path.join(root, f)
                if os.path.splitext(f)[1] == '.tsv':
                    contents = file_utils.read_file(file_path)
                    self.find_invalid_links(root, f, contents)

        file_list = os.listdir(source_dir)
        if  len(self.rc.projects) != 1: # Many repos are intentionally just one book
            for dir in BOOK_NUMBERS:
                found_file = False
                for file_name in file_list:
                    if file_name.endswith('.tsv') and dir.upper() in file_name:
                        found_file = True
                        break
                if not found_file:
                    self.log.warning(f"Missing tN tsv book: '{dir}'")

        # Now check tabs and C:V numbers
        MAX_ERROR_COUNT = 20
        for filename in sorted(file_list):
            if not filename.endswith('.tsv'): continue # Skip other files
            error_count = 0
            AppSettings.logger.info(f"Linting {filename}…")
            tsv_filepath = os.path.join(source_dir, filename)
            started = False
            expectedB = filename[-7:-4]
            lastC = lastV = C = V = '0'
            with open(tsv_filepath, 'rt') as tsv_file:
                for tsv_line in tsv_file:
                    tsv_line = tsv_line.rstrip('\n')
                    tab_count = tsv_line.count('\t')
                    if not started:
                        # AppSettings.logger.debug(f"TSV header line is '{tsv_line}'")
                        if tsv_line != 'Book	Chapter	Verse	OrigQuote	OccurrenceNote':
                            self.log.warning(f"Unexpected TSV header line: '{tsv_line}' in {filename}")
                            error_count += 1
                        started = True
                    elif tab_count != TnTsvLinter.EXPECTED_TAB_COUNT:
                        self.log.warning(f"Bad {expectedB} line near {C}:{V} with {tab_count} tabs (expected {TnTsvLinter.EXPECTED_TAB_COUNT})")
                        B = C = V = _OrigQuote = OccurrenceNote = None
                        error_count += 1
                    else:
                        B, C, V, _OrigQuote, OccurrenceNote = tsv_line.split('\t')
                        if B != expectedB:
                            self.log.warning(f"Unexpected '{B}' in '{tsv_line}' in {filename}")
                        if not C:
                            self.log.warning(f"Missing chapter number after {lastC}:{lastV} in {filename}")
                        elif not C.isdigit() and C not in ('front','back'):
                            self.log.warning(f"Bad '{C}' chapter number near verse {V} in {filename}")
                        elif C.isdigit() and lastC.isdigit():
                            lastCint, Cint = int(lastC), int(C)
                            if Cint < lastCint:
                                self.log.warning(f"Decrementing '{C}' chapter number after {lastC} in {filename}")
                            elif Cint > lastCint+1:
                                self.log.warning(f"Missing chapter number {lastCint+1} after {lastC} in {filename}")
                        if C == lastC: # still in the same chapter
                            if not V.isdigit():
                                self.log.warning(f"Bad '{V}' verse number in chapter {C} in {filename}")
                            elif lastV.isdigit():
                                lastVint, Vint = int(lastV), int(V)
                                if Vint < lastVint:
                                    self.log.warning(f"Decrementing '{V}' verse number after {lastV} in chapter {C} in {filename}")
                                # NOTE: Disabled because missing verse notes are expected
                                # elif Vint > lastVint+1:
                                    # self.log.warning(f"Missing verse number {lastVint+1} after {lastV} in chapter {C} in {filename}")
                        else: # just started a new chapter
                            if not V.isdigit() and V != 'intro':
                                self.log.warning(f"Bad '{V}' verse number in start of chapter {C} in {filename}")
                        # if OrigQuote and need_to_check_quotes:
                        #     try: self.check_original_language_quotes(B,C,V,OrigQuote)
                        #     except Exception as e:
                        #         self.log.warning(f"{B} {C}:{V} Unable to check original language quotes: {e}")
                        if OccurrenceNote:
                            left_count, right_count = OccurrenceNote.count('['), OccurrenceNote.count(']')
                            if left_count != right_count:
                                self.log.warning(f"Unmatched square brackets at {B} {C}:{V} in '{OccurrenceNote}'")
                            self.check_markdown(py_markdown_linter, OccurrenceNote, f'{B} {C}:{V}')
                        lastC, lastV = C, V
                        if lastC == 'front': lastC = '0'
                        elif lastC == 'back': lastC = '999'
                    if error_count > MAX_ERROR_COUNT:
                        AppSettings.logger.critical("TnTsvLinter: Too many TSV count errors -- aborting!")
                        break

        # if prefix and debug_mode_flag:
        #     AppSettings.logger.debug(f"Temp folder '{self.preload_dir}' has been left on disk for debugging!")
        # else:
        #     file_utils.remove_tree(self.preload_dir)
        return True
    # end of TnTsvLinter.lint()


    def check_markdown(self, mdLinter:PyMarkdownLinter, markdown_string:str, reference:str) -> None:
        """
        Checks the header progressions in the markdown string
        """
        # New code using unfinished PyMarkdownLinter
        linter_warnings = mdLinter.lint(markdown_string.replace('<br>','\n'))
        if linter_warnings:
            AppSettings.logger.debug(f"Markdown linter result count for {reference} = {len(linter_warnings):,}.")
            for rule_violation in linter_warnings:
                self.log.warning(f"{reference} line {rule_violation.line_nr}: {rule_violation.message}")

        # Also, our manual checks (since the above is unfinished)
        header_level = 0
        for bit in markdown_string.split('<br>'):
            if bit.startswith('# '):
                header_level = 1
            elif bit.startswith('## '):
                if header_level < 1:
                    self.log.warning(f"Markdown header jumped directly to level 2 at {reference}")
                header_level = 2
            elif bit.startswith('### '):
                if header_level < 2:
                    self.log.warning(f"Markdown header jumped directly to level 3 at {reference}")
                header_level = 3
            elif bit.startswith('#### '):
                if header_level < 3:
                    self.log.warning(f"Markdown header jumped directly to level 4 at {reference}")
                header_level = 4
            elif bit.startswith('##### '):
                if header_level < 4:
                    self.log.warning(f"Markdown header jumped directly to level 5 at {reference}")
                header_level = 5
            elif bit.startswith('#'):
                self.log.warning(f"Badly formatted markdown header at {reference}")

        self.check_punctuation_pairs(markdown_string, reference, allow_close_parenthesis_points=True) # Uses 1) for lists of points!
    # end of TnTsvLinter.check_markdown function


    def find_invalid_links(self, folder:str, filename:str, contents:str) -> None:
        # AppSettings.logger.debug(f"TnTsvLinter.find_invalid_links( {folder}, {f}, {contents} ) …")
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
                    a = self.get_file_link(filename, folder)
                    self.log.warning(f"{a}: contains invalid link: ({link})")
    # end of TnTsvLinter.find_invalid_links function

    def get_file_link(self, filename:str, folder:str) -> str:
        parts = folder.split(self.source_dir)
        sub_path = self.source_dir  # default
        if len(parts) == 2:
            sub_path = parts[1][1:]
        self.repo_owner = self.repo_name = '' # WE DON'T KNOW THIS STUFF
        url = f'https://git.door43.org/{self.repo_owner}/{self.repo_name}/src/master/{sub_path}/{filename}'
        a = f'<a href="{url}">{sub_path}/{filename}</a>'
        return a
    # end of TnTsvLinter.get_file_link function
# end of TnTsvLinter class
