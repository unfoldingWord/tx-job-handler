import os
import traceback
from linters.linter import Linter
from door43_tools.page_metrics import PageMetrics
from tx_usfm_tools import verifyUSFM, books
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
            self.log.warning(f"Invalid language code: {lang_code}")

        for root, _dirs, files in os.walk(self.source_dir):
            for filename in sorted(files):
                if os.path.splitext(filename)[1].lower() != '.usfm':  # only usfm files
                    continue

                if self.single_file and (filename != self.single_file):
                    continue

                GlobalSettings.logger.debug(f"Linting {filename} …")
                file_path = os.path.join(root, filename)
                sub_path = '.' + file_path[len(self.source_dir):]
                self.parse_file(file_path, sub_path, filename)

        if not self.found_books:
            self.log.warning("No translations found")

        return True


    def parse_file(self, file_path, sub_path, file_name):

        book_code, book_full_name = self.get_book_ids(file_name)

        try:
            f = open(file_path, 'rt')
            book_text = f.read().lstrip()
            if book_text:
                self.parse_usfm_text(sub_path, file_name, book_text, book_full_name, book_code)
            else:
                self.log.warning(f"USFM book '{file_name}' seems empty")
        except Exception as e:
            self.log.warning(f"Failed to open USFM book '{file_name}', exception: {e}")
    # end of parse_file function


    @staticmethod
    def get_book_ids(usfm_filename):
        """
        Given the name of a usfm file,
            try to determine the book_code (as well as returning the fullname part without the extension)

        Everything returned is UPPERCASE.
        """
        file_name_parts = usfm_filename.split('.')
        book_full_name = file_name_parts[0].upper()

        book_code = book_full_name
        book_name_parts = book_full_name.split('-')
        if len(book_name_parts) > 1:
            book_code = book_name_parts[1]
        # Expected method is above -- the code below tries to cope with human variations
        if book_code not in books.silNames:
            book_code = None
            GlobalSettings.logger.debug(f"get_book_ids({usfm_filename}) try1 seemed to fail with book_code='{book_code}'")
            for book_code in book_name_parts:
                if book_code in books.silNames:
                    break
        if book_code not in books.silNames:
            book_code = None
            GlobalSettings.logger.debug(f"get_book_ids({usfm_filename}) try2 seemed to fail with book_code='{book_code}'")
            for book_code in book_full_name.split('_'):
                if book_code in books.silNames:
                    break
        if book_code not in books.silNames:
            book_code = None
            GlobalSettings.logger.debug(f"get_book_ids({usfm_filename}) try3 seemed to fail with book_code='{book_code}'")
            for book_code in book_full_name.replace('-','_').split('_'):
                if book_code in books.silNames:
                    break
        if book_code is None:
            book_code = book_full_name # again
        if book_code not in books.silNames:
            GlobalSettings.logger.warning(f"get_book_ids({usfm_filename}) try4 seemed to fail with book_code='{book_code}'")

        return book_code, book_full_name
    # end of get_book_ids function


    def parse_usfm_text(self, sub_path, file_name, book_text, book_full_name, book_code):
        try:
            lang_code = self.rc.resource.language.identifier
            errors, book_code = verifyUSFM.verify_contents_quiet(book_text, book_full_name, book_code, lang_code)

            # if found_book_code:
            #     book_code = found_book_code

            if book_code:
                if book_code in self.found_books:
                    self.log.warning(f"File '{sub_path}' has same code '{book_code}' as previous file")
                self.found_books.append(book_code)

            if errors:
                for error in errors:
                    self.log.warning(error)

        except Exception as e: # for debugging
            self.log.warning(f"Failed to verify book '{file_name}', exception: {e}")
            print(f"Failed to verify USFM book '{file_name}', exception: {e}: {traceback.format_exc()}")
    # end of parse_usfm_text function
# end of UsfmLinter class