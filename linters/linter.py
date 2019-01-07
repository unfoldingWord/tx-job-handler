import json
import os
import tempfile
import traceback
import requests
from datetime import datetime

from rq_settings import prefix, debug_mode_flag
from general_tools.url_utils import download_file
from general_tools.file_utils import unzip, remove_tree
from linters.lint_logger import LintLogger
from resource_container.ResourceContainer import RC
from global_settings.global_settings import GlobalSettings
from abc import ABCMeta, abstractmethod



class Linter(metaclass=ABCMeta):
    """
    """
    EXCLUDED_FILES = ['license.md', 'package.json', 'project.json', 'readme.md']

    def __init__(self, source_url=None, source_file=None, source_dir=None, commit_data=None,
                 lint_callback=None, identifier=None, s3_results_key=None, **kwargs):
        """
        :param string source_url: The main way to give Linter the files
        :param string source_file: If set, will just unzip this local file
        :param string source_dir: If set, will just use this directory
        :param dict commit_data: Can get the changes, commit_url, etc from this
        :param string lint_callback: If set, will do callback
        :param string identifier:
        :param string s3_results_key:
        :params dict kwargs: Seem to be ignored
        """
        GlobalSettings.logger.debug(f"Linter.__init__(url={source_url}, file={source_file},"
                                    f" dir={source_dir}, cd={commit_data}, callback={lint_callback},"
                                    f" id={identifier}, s3k={s3_results_key})")
        self.source_zip_url = source_url
        self.source_zip_file = source_file
        self.source_dir = source_dir
        self.commit_data = commit_data

        self.log = LintLogger()

        self.temp_dir = tempfile.mkdtemp(prefix='tX_JH_linter_' \
                                + datetime.utcnow().strftime('%Y-%m-%d_%H:%M:%S_'))

        self.repo_owner = ''
        self.repo_name = ''
        if self.commit_data:
            self.repo_name = self.commit_data['repository']['name']
            self.repo_owner = self.commit_data['repository']['owner']['username']
        self.rc = None   # Constructed later when we know we have a source_dir

        self.callback = lint_callback
        self.callback_status = 0
        self.callback_results = None
        self.identifier = identifier
        if self.callback and not identifier:
            GlobalSettings.logger.error("Identity not given for callback")
        self.s3_results_key = s3_results_key
        if self.callback and not s3_results_key:
            GlobalSettings.logger.error("s3_results_key not given for callback")

    def close(self):
        """delete temp files"""
        # print("Linter close() was called!")
        if prefix and debug_mode_flag:
            GlobalSettings.logger.debug(f"Linter temp folder '{self.temp_dir}' has been left on disk for debugging!")
        else:
            remove_tree(self.temp_dir)

    # def __del__(self):
    #     print("Linter __del__() was called!")
    #     self.close()

    @abstractmethod
    def lint(self):
        """
        Dummy function for linters.

        Returns true if it was able to lint the files
        :return bool:
        """
        raise NotImplementedError()

    def run(self):
        """
        Run common handling for all linters,and then calls the lint() function
        """
        #GlobalSettings.logger.debug("Linter.run()")
        success = False
        try:
            # Download file if a source_zip_url was given
            if self.source_zip_url:
                GlobalSettings.logger.debug("Linting url: " + self.source_zip_url)
                self.download_archive()
            # unzip the input archive if a source_zip_file exists
            if self.source_zip_file:
                GlobalSettings.logger.debug("Linting zip: " + self.source_zip_file)
                self.unzip_archive()
            # lint files
            if self.source_dir:
                self.rc = RC(directory=self.source_dir)
                #GlobalSettings.logger.debug(f"Got RC = {self.rc}")
                GlobalSettings.logger.debug(f"Linting '{self.source_dir}' files…")
                success = self.lint()
                # GlobalSettings.logger.debug("Linting finished.")
        except Exception as e:
            message = f"Linting process ended abnormally: {e}"
            GlobalSettings.logger.error(message)
            self.log.warnings.append(message)
            GlobalSettings.logger.error('{0}: {1}'.format(str(e), traceback.format_exc()))
        warnings = self.log.warnings
        if len(warnings) > 200:  # sanity check so we don't overflow callback size limits
            warnings = warnings[0:199]
            msg = f"Warnings truncated for {self.s3_results_key}"
            GlobalSettings.logger.debug(msg)
            warnings.append(msg)
        results = {
            'identifier': self.identifier,
            'success': success,
            'warnings': warnings,
            's3_results_key': self.s3_results_key
        }

        if self.callback is not None:
            self.callback_results = results
            self.do_callback(self.callback, self.callback_results)

        GlobalSettings.logger.debug(f"Linter results: {results}")
        return results

    def download_archive(self):
        filename = self.source_zip_url.rpartition('/')[2]
        self.source_zip_file = os.path.join(self.temp_dir, filename)
        GlobalSettings.logger.debug("Downloading {0} to {1}".format(self.source_zip_url, self.source_zip_file))
        if not os.path.isfile(self.source_zip_file):
            try:
                download_file(self.source_zip_url, self.source_zip_file)
            finally:
                if not os.path.isfile(self.source_zip_file):
                    raise Exception(f"Failed to download {self.source_zip_url}")

    def unzip_archive(self):
        GlobalSettings.logger.debug(f"Unzipping {self.source_zip_file} to {self.temp_dir}")
        unzip(self.source_zip_file, self.temp_dir)
        dirs = [d for d in os.listdir(self.temp_dir) if os.path.isdir(os.path.join(self.temp_dir, d))]
        if len(dirs):
            self.source_dir = os.path.join(self.temp_dir, dirs[0])
        else:
            self.source_dir = self.temp_dir

    def do_callback(self, url, payload):
        if url.startswith('http'):
            headers = {"content-type": "application/json"}
            GlobalSettings.logger.debug('Making callback to {0} with payload:'.format(url))
            GlobalSettings.logger.debug(json.dumps(payload)[:256])
            response = requests.post(url, json=payload, headers=headers)
            self.callback_status = response.status_code
            if (self.callback_status >= 200) and (self.callback_status < 299):
                GlobalSettings.logger.debug('Callback finished.')
            else:
                GlobalSettings.logger.error('Error calling callback code {0}: {1}'.format(self.callback_status, response.reason))
        else:
            GlobalSettings.logger.error(f"Invalid callback url: {url}")
