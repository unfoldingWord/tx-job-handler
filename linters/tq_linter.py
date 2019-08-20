import os

from app_settings.app_settings import AppSettings
from linters.markdown_linter import MarkdownLinter
from door43_tools.bible_books import BOOK_NUMBERS


class TqLinter(MarkdownLinter):

    def lint(self):
        """
        Checks for issues with translationQuestions

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.md)
        :return bool:
        """
        # import logging # Can be used for debugging tests
        # AppSettings.logger.setLevel(logging.DEBUG)
        AppSettings.logger.debug(f"TqLinter.lint() with '{self.source_dir}' containing {os.listdir(self.source_dir)}")

        for book_abbreviation in BOOK_NUMBERS: # 3-characters, lowercase
            found_book_file = False
            link = self.get_link_for_book(f'{BOOK_NUMBERS[book_abbreviation]}-{book_abbreviation.upper()}')
            # AppSettings.logger.debug(f"Link is '{link}' for book '{book_abbreviation}''")

            # Look in the given source_dir first
            search_book_string = f'-{book_abbreviation.upper()}'
            for root, _dirs, files in os.walk(self.source_dir):
                for this_filename in files:
                    # AppSettings.logger.debug(f"this_filename1 is '{this_filename}'")
                    parts = os.path.splitext(this_filename)
                    # AppSettings.logger.debug(f"parts1 is '{parts}'")
                    if (len(parts) > 1) and parts[1] == '.md' \
                    and search_book_string in parts[0]:
                        # AppSettings.logger.debug(f"Found1 '{book_abbreviation}' with '{this_filename}'")
                        found_book_file = True
                        break
                if found_book_file: break
            if found_book_file: continue

            # NOTE: The below is where the original tX-Manager expected to find the files
            # Look in individual book folders
            file_path = os.path.join(self.source_dir, link)
            # AppSettings.logger.debug(f"file_path is '{file_path}'")
            for root, dirs, files in os.walk(file_path):
                # print(root, dirs, files)
                if root == file_path: continue  # Skip book folder
                for this_filename in files:
                    # AppSettings.logger.debug(f"this_filename2 is '{this_filename}'")
                    parts = os.path.splitext(this_filename)
                    # AppSettings.logger.debug(f"parts2 is '{parts}'")
                    if (len(parts) > 1) and (parts[1] == '.md'):
                        # AppSettings.logger.debug(f"Found2 '{book_abbreviation}' with '{this_filename}'")
                        found_book_file = True
                        break
                if found_book_file: break

            if not found_book_file \
            and 'OBS' not in self.repo_subject \
            and len(self.rc.projects) != 1: # Many repos are intentionally just one book
                msg = f"Missing tQ book: '{link}'"
                AppSettings.logger.debug(msg)
                self.log.warnings.append(msg)
        # print(self.log.warnings)

        return super(TqLinter, self).lint()  # Runs checks on Markdown, using the markdown linter

    def get_link_for_book(self, book):
        parts = book.split('-')
        link = book
        if len(parts) > 1:
            link = parts[1].lower()
        return link
