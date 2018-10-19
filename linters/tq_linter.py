import os

from global_settings.global_settings import GlobalSettings
from preprocessors.preprocessors import TqPreprocessor
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
        GlobalSettings.logger.debug(f"TqLinter.lint() with '{self.source_dir}' containing {os.listdir(self.source_dir)}")

        for book in BOOK_NUMBERS:
            found_files = False
            link = self.get_link_for_book(f'{BOOK_NUMBERS[book]}-{book.upper()}')
            file_path = os.path.join(self.source_dir, link)
            for root, dirs, files in os.walk(file_path):
                if root == file_path:
                    continue  # skip book folder

                for file in files:
                    parts = os.path.splitext(file)
                    if (len(parts) > 1) and (parts[1] == '.md'):
                        found_files = True
                        break

                if found_files:
                    break

            if not found_files:
                msg = f"missing book: '{link}'"
                self.log.warnings.append(msg)
                GlobalSettings.logger.debug(msg)

        return super(TqLinter, self).lint()  # Runs checks on Markdown, using the markdown linter

    def get_link_for_book(self, book):
        parts = book.split('-')
        link = book
        if len(parts) > 1:
            link = parts[1].lower()
        return link
