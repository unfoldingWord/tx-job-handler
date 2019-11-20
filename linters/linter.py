import json
import os
import tempfile
import traceback
from datetime import datetime
from abc import ABCMeta, abstractmethod
from typing import Any, Optional, Union

from app_settings.app_settings import AppSettings
from rq_settings import prefix, debug_mode_flag
from general_tools.url_utils import download_file
from general_tools.file_utils import unzip, remove_tree
from linters.lint_logger import LintLogger
from resource_container.ResourceContainer import RC



class Linter(metaclass=ABCMeta):
    """
    """
    EXCLUDED_FILES = ['license.md', 'package.json', 'project.json', 'readme.md']

    def __init__(self, repo_subject:str, source_dir:str) -> None:
        """
        :param string source_dir: If set, will just use this directory
        """
        AppSettings.logger.debug(f"Linter.__init__(subj={repo_subject}, dir={source_dir})")
        self.repo_subject = repo_subject
        self.source_dir = source_dir

        self.log = LintLogger()

        self.temp_dir = tempfile.mkdtemp(prefix=f'tX_{repo_subject}_linter_' \
                                + datetime.utcnow().strftime('%Y-%m-%d_%H:%M:%S_'))

        # TODO: Why do we need this? How does it help?
        self.rc:Optional[RC] = None   # Constructed later when we know we have a source_dir
    # end of __init__ function


    def close(self) -> None:
        """delete temp files"""
        # print("Linter close() was called!")
        if prefix and debug_mode_flag:
            AppSettings.logger.debug(f"Linter temp folder '{self.temp_dir}' has been left on disk for debugging!")
        else:
            remove_tree(self.temp_dir)
    # end of close()


    # def __del__(self):
    #     print("Linter __del__() was called!")
    #     self.close()


    @abstractmethod
    def lint(self) -> None:
        """
        Dummy function for linters.

        Returns true if it was able to lint the files
        :return bool:
        """
        raise NotImplementedError()
    # end of lint()


    def run(self) -> dict:
        """
        Run common handling for all linters:
            downloads and unzips the source url (if given)
            and then calls the lint() function
        """
        #AppSettings.logger.debug("Linter.run()")
        success = False
        try:
            # Download file if a source_zip_url was given
            # if self.source_zip_url:
            #     AppSettings.logger.debug("Linting url: " + self.source_zip_url)
            #     self.download_archive()
            # # unzip the input archive if a source_zip_file exists
            # if self.source_zip_file:
            #     AppSettings.logger.debug("Linting zip: " + self.source_zip_file)
            #     self.unzip_archive()
            # lint files
            # if self.source_dir:
            self.rc = RC(directory=self.source_dir)
            #AppSettings.logger.debug(f"Got RC = {self.rc}")
            AppSettings.logger.debug(f"Linting '{self.source_dir}' files…")
            success = self.lint()
            # AppSettings.logger.debug("Linting finished.")
        except Exception as e:
            message = f"Linting process ended abnormally: {e}"
            AppSettings.logger.error(message)
            self.log.warnings.append(message)
            AppSettings.logger.error(f'{e}: {traceback.format_exc()}')
        warnings = self.log.warnings
        if len(warnings) > 200:  # sanity check so we don't overflow callback size limits
            warnings = warnings[:190]
            warnings.append("………………")
            warnings.extend(self.log.warnings[-9:])
            # msg = f"Warnings truncated (from {len(self.log.warnings)} to {len(warnings)})"
            msg = f"Linter warnings reduced from {len(self.log.warnings):,} to {len(warnings)}"
            AppSettings.logger.debug(f"Linter {msg}")
            warnings.append(msg)

        results = {
            'success': success,
            'warnings': warnings,
            }
        AppSettings.logger.debug(f"Linter results: {results}")
        return results
    # end of run()


    # def download_archive(self) -> None:
    #     filename = self.source_zip_url.rpartition('/')[2]
    #     self.source_zip_file = os.path.join(self.temp_dir, filename)
    #     AppSettings.logger.debug("Downloading {0} to {1}".format(self.source_zip_url, self.source_zip_file))
    #     if not os.path.isfile(self.source_zip_file):
    #         try:
    #             download_file(self.source_zip_url, self.source_zip_file)
    #         finally:
    #             if not os.path.isfile(self.source_zip_file):
    #                 raise Exception(f"Failed to download {self.source_zip_url}")
    # # end of download_archive()


    # def unzip_archive(self) -> None:
    #     AppSettings.logger.debug(f"Unzipping {self.source_zip_file} to {self.temp_dir}")
    #     unzip(self.source_zip_file, self.temp_dir)
    #     dirs = [d for d in os.listdir(self.temp_dir) if os.path.isdir(os.path.join(self.temp_dir, d))]
    #     if dirs:
    #         self.source_dir = os.path.join(self.temp_dir, dirs[0])
    #     else:
    #         self.source_dir = self.temp_dir
    # # end of unzip_archive()
#end of linter.py