import os
import json
from html.parser import HTMLParser
from typing import Dict, List, Any

from rq_settings import prefix, debug_mode_flag
from linters.linter import Linter
from aws_tools.lambda_handler import LambdaHandler
from general_tools.file_utils import read_file, get_files
from app_settings.app_settings import AppSettings

from linters.py_markdown_linter.lint import MarkdownLinter as PyMarkdownLinter
from linters.py_markdown_linter.config import LintConfig



class MarkdownLinter(Linter):

    def __init__(self, *args, **kwargs) -> None:
        super(MarkdownLinter, self).__init__(*args, **kwargs)
        self.single_file = None
        self.single_dir = None


    def lint(self) -> bool:
        """
        Checks for issues with all Markdown project, such as bad use of headers, bullets, etc.

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.md)
        :return bool:
        """
        AppSettings.logger.debug("MarkdownLinter.lint()")

        # Do some preliminary checks on the files
        for filename in self.get_files(relative_paths=True):
            with open( os.path.join(self.source_dir, filename), 'rt') as md_file:
                file_contents = md_file.read()
            self.check_pairs(file_contents, filename.replace('.md',''))


        md_data = self.get_strings() # Used for AWS Lambda call
        # Determine approximate length of the payload data
        payloadString = json.dumps(md_data) # (it doesn't include 'config' yet)
        if not isinstance(payloadString, str): # then it must be Python3 bytes
            payloadString = payloadString.decode()
        estimated_payload_length = len(payloadString) + 335 # Allow for 'config' strings (included later)
        AppSettings.logger.debug(f"Approx length of Markdown Linter payload = {estimated_payload_length:,} characters.")
        payload_oversize_flag = estimated_payload_length > 6_291_456 # 6 MB -- AWS Lambda call will fail
        if payload_oversize_flag:
            AppSettings.logger.warning(f"Oversize Markdown Linter payload = {estimated_payload_length:,} characters.")

        test_pyLinter = prefix and debug_mode_flag # True: always use new Python linter; False: mostly use AWS Lambda call
        if test_pyLinter or payload_oversize_flag:
            # New code using unfinished PyMarkdownLinter
            AppSettings.logger.info("Invoking (unfinished) PyMarkdownLinter…")
            lint_config = LintConfig()
            for rule_id in ('MD009', 'MD010', 'MD013'): # Ignore
                lint_config.disable_rule_by_id(rule_id)
            py_markdown_linter = PyMarkdownLinter(lint_config)
            for filename in self.get_files(relative_paths=True):
                with open( os.path.join(self.source_dir, filename), 'rt') as md_file:
                    linter_warnings = py_markdown_linter.lint(md_file.read())
                if linter_warnings:
                    AppSettings.logger.debug(f"Markdown linter result count for {filename} = {len(linter_warnings):,}.")
                    for rule_violation in linter_warnings:
                        self.log.warning(f"{filename.replace('.md','')} line {rule_violation.line_nr}: {rule_violation.message}")

        else: # old (tx-Manager) code using AWS Lambda node.js call
            AppSettings.logger.info("Invoking Node.js linter via AWS Lambda call…")
            # print(len(md_data), md_data)
            # AppSettings.logger.debug(f"Size of markdown data = {len(md_data)}") # Useless -- always shows 1
            lint_data = self.invoke_markdown_linter(self.get_invoke_payload(md_data))
            if not lint_data:
                return False
            # RJH: What is this code doing? Why are warnings expressed as HTML segments here???
            self.repo_owner = self.repo_name = '' # WE DON'T KNOW THIS STUFF
            for f in lint_data.keys():
                file_url = f'https://git.door43.org/{self.repo_owner}/{self.rc.repo_name}/src/master/{f}'
                for item in lint_data[f]:
                    error_context = ''
                    if item['errorContext']:
                        error_context = f'See "{self.strip_tags(item["errorContext"])}"'
                    line = '<a href="{0}" target="_blank">{1}</a> - Line {2}: {3}. {4}'. \
                        format(file_url, f, item['lineNumber'], item['ruleDescription'], error_context)
                    self.log.warning(line)
        return True


    def get_files(self, relative_paths:bool) -> List[str]:
        """
        relative_paths can be True or False

        Returns a sorted list of .md files to be processed
        """
        if self.single_dir:
            dir_path = os.path.join(self.source_dir, self.single_dir)
            sub_files = sorted(get_files(directory=dir_path, relative_paths=relative_paths, exclude=self.EXCLUDED_FILES,
                                         extensions=['.md']))
            files = []
            for f in sub_files:
                files.append(os.path.join(self.single_dir, f))
        else:
            files = sorted(get_files(directory=self.source_dir, relative_paths=relative_paths, exclude=self.EXCLUDED_FILES,
                                     extensions=['.md']))
        return files


    def get_strings(self) -> List[str]:
        strings = {}
        for filename in self.get_files(relative_paths=True):
            filepath = os.path.join(self.source_dir, filename)
            try: text = read_file(filepath)
            except Exception as e:
                self.log.warning(f"Error reading {filename}: {e}")
            strings[filename] = text
        return strings


    def get_invoke_payload(self, strings:Dict[str,Any]) -> Dict[str,Any]:
        return {
            'options': {
                'strings': strings,
                'config': {
                    'default': True,
                    'no-hard-tabs': False,  # MD010
                    'whitespace': False,  # MD009, MD010, MD012, MD027, MD028, MD030, MD037, MD038, MD039
                    'line-length': False,  # MD013
                    'no-inline-html': False,  # MD033
                    'no-duplicate-header': False,  # MD024
                    'single-h1': False,  # MD025
                    'no-trailing-punctuation': False,  # MD026
                    'no-emphasis-as-header': False,  # MD036
                    'first-header-h1': False,  # MD002
                    'first-line-h1': False,  # MD041
                    'no-bare-urls': False,  # MD034
                }
            }
        }

    def invoke_markdown_linter(self, payload:Dict[str,Any]):
        #AppSettings.logger.debug(f"MarkdownLinter.invoke_markdown_linter( {payload.keys()}/{len(payload['options'])}/{payload['options'].keys()} )")
        AppSettings.logger.debug(f"MarkdownLinter.invoke_markdown_linter( {payload['options'].keys()}/{payload['options']['config']}/{len(payload['options']['strings'])} )")
        lambda_handler = LambdaHandler()
        lint_function = f'{AppSettings.prefix}tx_markdown_linter'
        # AppSettings.logger.debug(f"Size of {self.s3_results_key} lint data={len(payload)}") # Useless data -- always shows None/1
        response = lambda_handler.invoke(lint_function, payload)
        if 'errorMessage' in response:
            AppSettings.logger.error(response['errorMessage'])
            return None
        elif 'Payload' in response:
            return json.loads(response['Payload'].read())

    def get_dir_for_book(self, book: str) -> str:
        parts = book.split('-')
        link = book
        if len(parts) > 1:
            link = parts[1].lower()
        return link

    @staticmethod
    def strip_tags(html: str) -> str:
        ts = TagStripper()
        ts.feed(html)
        return ts.get_data()


class TagStripper(HTMLParser):

    def __init__(self) -> None:
        self.reset()
        self.fed: list = []
        super().__init__(convert_charrefs=True) # See https://stackoverflow.com/questions/48203228/python-3-4-deprecationwarning-convert-charrefs

    def handle_data(self, d: str) -> None:
        self.fed.append(d)

    def get_data(self) -> str:
        return ''.join(self.fed)
