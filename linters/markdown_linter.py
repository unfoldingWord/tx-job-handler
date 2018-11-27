import os
import json
from html.parser import HTMLParser

from linters.linter import Linter
from aws_tools.lambda_handler import LambdaHandler
from general_tools.file_utils import read_file, get_files
from global_settings.global_settings import GlobalSettings

from linters.py_markdown_linter.lint import MarkdownLinter as PyMarkdownLinter
from linters.py_markdown_linter.config import LintConfig

class MarkdownLinter(Linter):

    def __init__(self, *args, **kwargs):
        super(MarkdownLinter, self).__init__(*args, **kwargs)
        self.single_file = None
        self.single_dir = None

    def lint(self):
        """
        Checks for issues with all Markdown project, such as bad use of headers, bullets, etc.

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of source files (.md)
        :return bool:
        """
        GlobalSettings.logger.debug("MarkdownLinter.lint()")

        if 0: # new code using PyMarkdownLinter
            GlobalSettings.logger.info("Invoking (unfinished) PyMarkdownLinter…")
            lint_config = LintConfig()
            for rule_id in ('MD009', 'MD010', 'MD013'): # Ignore
                lint_config.disable_rule_by_id(rule_id)
            linter = PyMarkdownLinter(lint_config)
            for filename in self.get_files(relative_paths=True):
                with open( os.path.join(self.source_dir, filename), 'rt') as md_file:
                    linter_warnings = linter.lint(md_file.read())
                if linter_warnings:
                    GlobalSettings.logger.debug(f"Markdown linter result count for {filename} = {len(linter_warnings):,}.")
                    for rule_violation in linter_warnings:
                        self.log.warning(f"{filename.replace('.md','')} line {rule_violation.line_nr}: {rule_violation.message}")

        else: # old (tx-Manager) code using AWS Lambda node.js call
            GlobalSettings.logger.info("Invoking Node.js linter via AWS Lambda call…")
            md_data = self.get_strings()
            # print(len(md_data), md_data)
            # GlobalSettings.logger.debug(f"Size of markdown data = {len(md_data)}") # Useless -- always shows 1
            lint_data = self.invoke_markdown_linter(self.get_invoke_payload(md_data))
            if not lint_data:
                return False
            # What is this code doing? Why are warnings expressed as HTML segments here???
            for f in lint_data.keys():
                file_url = f'https://git.door43.org/{self.repo_owner}/{self.rc.repo_name}/src/master/{f}'
                for item in lint_data[f]:
                    error_context = ''
                    if item['errorContext']:
                        error_context = 'See "{0}"'.format(self.strip_tags(item['errorContext']))
                    line = '<a href="{0}" target="_blank">{1}</a> - Line {2}: {3}. {4}'. \
                        format(file_url, f, item['lineNumber'], item['ruleDescription'], error_context)
                    self.log.warning(line)
        return True

    def get_files(self, relative_paths):
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

    def get_strings(self):
        strings = {}
        for f in self.get_files(relative_paths=True):
            path = os.path.join(self.source_dir, f)
            text = read_file(path)
            strings[f] = text
        return strings

    def get_invoke_payload(self, strings):
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

    def invoke_markdown_linter(self, payload):
        #GlobalSettings.logger.debug(f"MarkdownLinter.invoke_markdown_linter( {payload.keys()}/{len(payload['options'])}/{payload['options'].keys()} )")
        GlobalSettings.logger.debug(f"MarkdownLinter.invoke_markdown_linter( {payload['options'].keys()}/{payload['options']['config']}/{len(payload['options']['strings'])} )")
        lambda_handler = LambdaHandler()
        lint_function = f'{GlobalSettings.prefix}tx_markdown_linter'
        # GlobalSettings.logger.debug(f"Size of {self.s3_results_key} lint data={len(payload)}") # Useless data -- always shows None/1
        response = lambda_handler.invoke(lint_function, payload)
        if 'errorMessage' in response:
            GlobalSettings.logger.error(response['errorMessage'])
            return None
        elif 'Payload' in response:
            return json.loads(response['Payload'].read())

    def get_dir_for_book(self, book):
        parts = book.split('-')
        link = book
        if len(parts) > 1:
            link = parts[1].lower()
        return link

    @staticmethod
    def strip_tags(html):
        ts = TagStripper()
        ts.feed(html)
        return ts.get_data()


class TagStripper(HTMLParser):

    def __init__(self):
        self.reset()
        self.fed = []
        super().__init__(convert_charrefs=True) # See https://stackoverflow.com/questions/48203228/python-3-4-deprecationwarning-convert-charrefs

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)
