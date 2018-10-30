import os
from linters.linter import Linter
from door43_tools.page_metrics import PageMetrics
from tx_usfm_tools import verifyUSFM
from global_settings.global_settings import GlobalSettings


class UsfmLinter(Linter):

    def __init__(self, single_file=None, *args, **kwargs):
        self.single_file = single_file
        self.found_books = []
        super(UsfmLinter, self).__init__(*args, **kwargs)

    def lint(self):
        """
        Checks for issues with all Bibles, such as missing books or chapters

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of .usfm files
        :return bool:
        """

        lang_code = self.rc.resource.language.identifier
        valid_lang_code = PageMetrics().validate_language_code(lang_code)
        if not valid_lang_code:
            self.log.warning("Invalid language code: " + lang_code)

        for root, dirs, files in os.walk(self.source_dir):
            for f in files:
                if os.path.splitext(f)[1].lower() != '.usfm':  # only usfm files
                    continue

                if self.single_file and (f != self.single_file):
                    continue

                GlobalSettings.logger.debug("linting: " + f)
                file_path = os.path.join(root, f)
                sub_path = '.' + file_path[len(self.source_dir):]
                self.parse_file(file_path, sub_path, f)

        if not len(self.found_books):
            self.log.warning("No translations found")

        return True

    def parse_file(self, file_path, sub_path, file_name):

        book_code, book_full_name = self.get_book_ids(file_name)

        try:
            f = open(file_path, 'rt')
            book_text = f.read().lstrip()

            self.parse_usfm_text(sub_path, file_name, book_text, book_full_name, book_code)

        except Exception as e:
            self.log.warning(f"Failed to open book '{file_name}', exception: {e}")

    @staticmethod
    def get_book_ids(file_name):
        file_name_parts = file_name.split('.')
        book_full_name = file_name_parts[0].upper()
        book_code = book_full_name
        book_name_parts = book_full_name.split('-')
        if len(book_name_parts) > 1:
            book_code = book_name_parts[1]
        return book_code, book_full_name

    def parse_usfm_text(self, sub_path, file_name, book_text, book_full_name, book_code):
        try:
            lang_code = self.rc.resource.language.identifier
            errors, found_book_code = verifyUSFM.verify_contents_quiet(book_text, book_full_name, book_code, lang_code)

            if found_book_code:
                book_code = found_book_code

            if book_code:
                if book_code in self.found_books:
                    self.log.warning(f"File '{sub_path}' has same code '{book_code}' as previous file")
                self.found_books.append(book_code)

            if len(errors):
                for error in errors:
                    self.log.warning(error)

        except Exception as e:
            # for debugging
            self.log.warning(f"Failed to verify book '{file_name}', exception: {e}")
