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
from datetime import datetime
from dateutil import parser
from door43_tools.dcs_api import DcsApi
from collections import OrderedDict
from general_tools.file_utils import load_yaml_object

DEFAULT_OWNER = 'unfoldingWord'
DEFAULT_REF = 'master'
OWNERS = [DEFAULT_OWNER, 'STR', 'Door43-Catalog', 'PCET', 'EXEGETICAL-BCS']
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
        if api:
            self.api = api
        else:
            self.api = DcsApi()

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
            self._last_commit = self.api.get_last_commit(self.owner, self.repo_name, self.ref)
        return self._last_commit

    @property
    def last_commit_sha(self):
        if self.last_commit:
            return self.last_commit['sha'][0:10]
        else:
            return ''

    @property
    def last_commit_date(self):
        if self.last_commit:
            return parser.parse(self.last_commit['commit']['committer']['date']).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return ''

    @property
    def manifest(self):
        if not self._manifest:
            if self.repo_dir:
                self._manifest = load_yaml_object(os.path.join(self.repo_dir, 'manifest.yaml'))
            else:
                self._manifest = self.api.get_manifest(self.owner, self.repo_name)
        return self._manifest

    @property
    def identifier(self):
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
    def stage(self):
        if not self._catalog_entry:
            self._catalog_entry = self.api.get_catalog_entry(owner=self.owner, repo_name=self.repo_name, ref=self.ref)
        if self._catalog_entry:
            return self._catalog_entry['stage']
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
