#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
Class for a resource
"""
import os
import yaml
import base64
from dateutil import parser
from collections import OrderedDict
from general_tools.file_utils import load_yaml_object
from app_settings.app_settings import AppSettings
from dcs_api_client.rest import ApiException

DEFAULT_OWNER = 'unfoldingWord'
DEFAULT_REF = 'master'
OWNERS = [DEFAULT_OWNER, 'Door43-Catalog', 'STR', 'PCET', 'EXEGETICAL-BCS', 'ru_gl', 'ne_gl', 'hi_gl']
LOGO_MAP = {
    'sn': 'utn',
    'sq': 'utq',
    'ta': 'uta',
    'tn': 'utn',
    'tw': 'utw',
    'tq': 'utq',
    'obs-tn': 'obs',
    'obs-tq': 'obs',
    'obs-sn': 'obs',
    'obs-sn-sq': 'obs',
    'obs-sq': 'obs'
}


class Resource(object):

    def __init__(self, subject=None, owner=None, repo_name=None, ref=DEFAULT_REF, manifest=None,
                 zipball_url=None, repo_dir=None, api=None):
        self._subject = subject
        self.repo_name = repo_name
        self.ref = ref
        self.owner = owner
        self._manifest = manifest
        self.zipball_url = zipball_url
        self.repo_dir = repo_dir

        self._catalog_entry = None
        self._last_commit = None

    @property
    def subject(self):
        if not self._subject:
            self._subject = self.manifest['dublin_core']['subject']
        return self._subject

    @property
    def logo_url(self):
        if self.identifier in LOGO_MAP:
            logo = LOGO_MAP[self.identifier]
        else:
            logo = self.identifier
        return f'https://cdn.door43.org/assets/uw-icons/logo-{logo}-256.png'

    @property
    def logo_file(self):
        return os.path.basename(self.logo_url)

    @property
    def last_commit(self):
        if not self._last_commit:
            try:
                commits = AppSettings.repo_api.repo_get_all_commits(self.owner, self.repo_name, sha=self.ref, limit=1)                
                if commits and len(commits) > 0:
                    self._last_commit = commits[0]
            except ApiException as e:
                AppSettings.logger.critical("Exception when calling RepositoryApi->repo_get_all_commits: %s\n" % e) 
        return self._last_commit

    @property
    def last_commit_sha(self):
        if self.last_commit:
            return self.last_commit.sha[0:10]
        else:
            return ''

    @property
    def last_commit_date(self):
        if self.last_commit:
            return parser.parse(self.last_commit.commit.committer._date).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return ''

    @property
    def manifest(self):
        if not self._manifest:
            if self.repo_dir:
                self._manifest = load_yaml_object(os.path.join(self.repo_dir, 'manifest.yaml'))
            else:
                try:
                    response = AppSettings.repo_api.repo_get_contents(self.owner, self.repo_name, "manifest.yaml", ref=self.ref)
                    self._manifest = yaml.safe_load(base64.b64decode(response.content))
                except ApiException as e:
                    print("Exception when calling RepositoryApi->repo_get_raw_file: %s\n" % e)
        return self._manifest

    @property
    def identifier(self):
        if not self.manifest or 'dublin_core' not in self.manifest:
            return ""
        manifest_identifier = self.manifest['dublin_core']['identifier']
        if manifest_identifier and manifest_identifier.count('_'):
            return manifest_identifier.split('_')[1]
        else:
            return manifest_identifier

    @property
    def title(self):
        return self.manifest['dublin_core']['title']

    @property
    def language_title(self):
        return self.manifest['dublin_core']['language']['title']

    @property
    def language_id(self):
        return self.manifest['dublin_core']['language']['identifier']

    @property
    def language_direction(self):
        return self.manifest['dublin_core']['language']['direction']

    @property
    def simple_title(self):
        return self.title.replace('unfoldingWord® ', '')

    @property
    def type(self):
        return self.manifest['dublin_core']['type']

    @property
    def version(self):
        return self.manifest['dublin_core']['version']

    @property
    def publisher(self):
        return self.manifest['dublin_core']['publisher']

    @property
    def issued(self):
        return self.manifest['dublin_core']['issued']

    @property
    def contributors(self):
        return self.manifest['dublin_core']['contributor']

    @property
    def catalog_entry(self):
        if not self._catalog_entry:
            try:
                self._catalog_entry = AppSettings.catalog_api.catlog_get_entry(self.owner, self.repo_name, self.ref)
            except ApiException as e:
                print("Exception when calling V5Api->catalog_get_entry: %s\n" % e)
        return self._catalog_entry


    @property
    def stage(self):
        if self.catalog_entry:
            return self.catalog_entry.stage
        return None

    @property
    def relation(self):
        return self.manifest['dublin_core']['relation']

    @property
    def projects(self):
        return self.manifest['projects']

    def find_project(self, project_id):
        if self.projects:
            for project in self.projects:
                if project['identifier'] == project_id:
                    return project


class Resources(OrderedDict):
    @property
    def main(self) -> Resource:
        if len(self.items()):
            return list(self.values())[0]
        else:
            raise IndexError("Empty ordered dict")

    @property
    def first(self) -> Resource:
        return self.main
