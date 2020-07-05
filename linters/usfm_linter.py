from typing import Tuple, Optional
import os
import traceback
from linters.linter import Linter
from door43_tools.page_metrics import PageMetrics
from tx_usfm_tools import verifyUSFM, books
from app_settings.app_settings import AppSettings



# If they start a line
SHOULD_ALWAYS_HAVE_TEXT_MARKERS = ( # Put longest markers ahead of shorter ones
                            'id', 'usfm', 'ide', 'h', 'toc1','toc2','toc3,',
                            'is1','is', 'iot',
                            'ip',
                            'ms','ms1','ms2','ms3','ms', 'mr1','mr'
                            'c', 'v',
                            's1','s2','s3','s4', # Can't use 's' yet coz we have empty s5 fields
                            'zaln-s', 'w',
                            )



class UsfmLinter(Linter):


    def __init__(self, single_file:Optional[str]=None, *args, **kwargs) -> None:
        self.single_file = single_file
        self.found_books = []
        super(UsfmLinter, self).__init__(*args, **kwargs)


    def lint(self) -> bool:
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

                AppSettings.logger.debug(f"Linting {filename} …")
                file_path = os.path.join(root, filename)
                sub_path = '.' + file_path[len(self.source_dir):]
                self.parse_file(file_path, sub_path, filename)

        if not self.found_books:
            self.log.warning("No translations found")

        return True


    def parse_file(self, file_path:str, sub_path:str, file_name:str) -> None:

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
    def get_book_ids(usfm_filename:str) -> Tuple[str,str]:
        """
        Given the name of a usfm file,
            try to determine the book_code (as well as returning the fullname part without the extension)

        Everything returned is UPPERCASE.
        """
        file_name_parts = usfm_filename.split('.')
        assert len(file_name_parts) == 2 # Exactly one period in usfm_filename
        book_full_name = file_name_parts[0].upper()

        book_code = book_full_name
        if book_code.endswith('_BOOK'): book_code = book_code[:-5]
        if '-' in book_full_name: book_name_parts = book_full_name.split('-')
        else: book_name_parts = book_full_name.split('_')
        if len(book_name_parts) > 1:
            book_code = book_name_parts[1]
        # Expected method is above—the code below tries to cope with human variations
        if book_code not in books.silNames:
            book_code = None
            AppSettings.logger.debug(f"get_book_ids({usfm_filename}) try1 seemed to fail with book_code={book_code!r}")
            for book_code in book_name_parts:
                if book_code in books.silNames:
                    break
        if book_code not in books.silNames:
            book_code = None
            AppSettings.logger.debug(f"get_book_ids({usfm_filename}) try2 seemed to fail with book_code={book_code!r}")
            for book_code in book_full_name.split('_'):
                if book_code in books.silNames:
                    break
        if book_code not in books.silNames:
            book_code = None
            AppSettings.logger.debug(f"get_book_ids({usfm_filename}) try3 seemed to fail with book_code={book_code!r}")
            for book_code in book_full_name.replace('-','_').split('_'):
                if book_code in books.silNames:
                    break
        if book_code is None:
            book_code = book_full_name # again
        if book_code not in books.silNames:
            AppSettings.logger.warning(f"get_book_ids({usfm_filename}) try4 seemed to fail with book_code={book_code!r}")

        return book_code, book_full_name
    # end of get_book_ids function


    def parse_usfm_text(self, sub_path:str, file_name:str,
                                book_text:str, book_full_name:str, book_code:str) -> None:
        """
        """
        if not book_text:
            self.log.warning(f"{book_code} - No USFM text found")
            return

        try:
            lang_code = self.rc.resource.language.identifier
            errors, book_code = verifyUSFM.verify_contents_quiet(book_text, book_full_name, book_code, lang_code)

            # if found_book_code:
            #     book_code = found_book_code

            if book_code:
                if book_code in self.found_books:
                    self.log.warning(f"File '{sub_path}' has same code {book_code!r} as previous file")
                self.found_books.append(book_code)

            if errors:
                for error in errors:
                    self.log.warning(error)

        except Exception as e: # for debugging
            self.log.warning(f"Failed to verify book '{file_name}', exception: {e}")
            print(f"Failed to verify USFM book '{file_name}', exception: {e}: {traceback.format_exc()}")

        # RJH added checks for USFM lines without content (Dec 2019)
        # TODO: Ideally this should go in
        C = V = '0'
        for line in book_text.split('\n'):
            if line.startswith('\\'):
                if line.startswith('\\c '): C, V = line[3:], '0'
                elif line.startswith('\\v '):
                    ixSpace = line.find(' ', 3) # Find the end of the verse number
                    V = '?' if ixSpace==-1 else line[3:ixSpace]
                for marker in SHOULD_ALWAYS_HAVE_TEXT_MARKERS:
                    if line.startswith(f'\\{marker}'):
                        if len(line) <= len(marker) + 1: # 1 for backslash
                            self.log.warning(f"{book_code} {C}:{V} '{line}' line has no content")
                        elif len(line) < len(marker) + 5: # 1 for backslash and space + 3
                            # Shortest line is '\h Job', '\usfm 3.0'
                            self.log.warning(f"{book_code} {C}:{V} '{line}' line seems too short")
                        break
    # end of parse_usfm_text function
# end of UsfmLinter class
