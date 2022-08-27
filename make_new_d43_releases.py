#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

from distutils.file_util import write_file
from operator import truediv
import sys
import os
import tempfile
import dcs_api_client
import shutil
import argparse
import re
import ruamel.yaml
from git import Repo
from collections import OrderedDict
from pprint import pprint
from base64 import b64decode, b64encode
from os import getenv
from datetime import datetime
from dcs_api_client.rest import ApiException
from door43_tools.bible_books import BOOK_NAMES
from TWL_TSV6_insert_into_HebGrk import insert_twl_into_ol
from TQ_TSV7_to_MD import convert_tsv_tq_to_md_tq
from generate_pdf import generate_pdf

AWS_ACCESS_KEY_ID = getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = getenv("AWS_SECRET_ACCESS_KEY")
DCS_TOKEN = getenv("DCS_TOKEN")
DCS_DOMAIN = getenv("DCS_DOMAIN", "git.door43.org")
PUBLISH_DIR = getenv("PUBLISH_DIR", "/tmp/publish2")
PDFS_DIR = getenv("PDFS_DIR", "/tmp/pdfs2")
BOOKS_PUBLISHED = ["exo", "rut",  "ezr",  "neh",  "est",  "oba",  "jon",  "luk",  "jhn", "1co", "eph",  "php",  "col",  "1th",  "2th", "1ti",  "2ti",  "tit",  "phm",  "jas",  "1pe", "2pe",  "1jn",  "2jn",  "3jn", "jud"]
RESOURCES = ["uhb", "ugnt", "tw", "twl", "ult", "ust", "ta", "tq", "tn"]
NO_PDF_REPOS = ["uhb", "ugnt", "twl"]
D43_IS_FORK = ["tw", "ult", "ust", "ta", "tn"]
DATE = datetime.now().strftime('%Y-%m-%d')
YEAR = datetime.now().strftime('%Y')
BP_STAGING = 'bp_staging'

INVERTED_BOOK_NAMES = {v: k for k, v in BOOK_NAMES.items()}

import string
printable = string.ascii_letters + string.digits + string.punctuation + ' '
def hex_escape(s):
    return ''.join(c if c in printable else r'\x{0:02x}'.format(ord(c)) for c in s)


class Resource:

  def __init__(self, repo, repo_api):
    self.repo = repo
    self.repo_api = repo_api
    self._manifest = None

  @property
  def manifest(self):
    if not self._manifest:
      contents = self.repo_api.repo_get_contents(self.repo.owner.login, self.repo.name, filepath="manifest.yaml", ref=self.repo.default_branch)
      self._manifest = ruamel.yaml.round_trip_load(b64decode(contents.content), preserve_quotes=True)
    return self._manifest

  @property
  def version(self):
    return self.manifest['dublin_core']['version']

  def create_release(self):
      body = dcs_api_client.CreateReleaseOption(
        name=f'Version {self.version}',
        tag_name=f'v{self.version}',
        prerelease=False,
        draft=False,
        target_commitish="master",
      )
      resp = self.repo_api.repo_create_release('Door43-Catalog', self.repo.name, body=body)
      if not resp:
        print(f"FAILED TO CREATE/UPDATE RELEASE FOR Door43-Catalog/{self.repo.name}")
        sys.exit(1)


class Publisher:

  def __init__(self):
    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://{DCS_DOMAIN}/api/v1"
    self.repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

  def run(self):
    info = {}
    repos = self.repo_api.repo_search(owner="Door43-Catalog", limit=600).data
    print(len(repos))
    count = 0
    for repo in repos:
      repo = self.repo_api.repo_get(owner=repo.owner.login, repo=repo.name)
      if not hasattr(repo.catalog, "latest") or not repo.catalog.latest:
        continue
      resource = Resource(repo=repo, repo_api=self.repo_api)
      r_ver = None
      try:
        m_ver = str(resource.version)
      except:
        continue
      if hasattr(repo.catalog, "prod") and repo.catalog.prod:
        r_ver = repo.catalog.prod.branch_or_tag_name.lstrip('v')
      info[repo.name] = {
        'name': repo.full_name,
        'm_ver': m_ver,
        'r_ver': r_ver,
        'needs_release': not r_ver or (r_ver < m_ver),
        'resource': resource,
      }
      if not r_ver:
        try:
          self.repo_api.repo_get(owner="unfoldingWord", repo=repo.name)
          info[repo.name]["needs_release"] = False
          continue
        except:
          pass
        resp = self.repo_api.repo_search(repo=repo.name)
        if resp:
          matching_repos = resp.data
          for r in matching_repos:
            if r.owner.login in ("Door43-Catalog", "translate_test", "STR", "test_org", "test_org2", "Sample_Org", "d43", "bp_staging", "DokuWiki", "richmahn", "russp41"):
              continue
            r = self.repo_api.repo_get(owner=r.owner.login, repo=r.name)
            if not hasattr(r.catalog, "latest") or not r.catalog.latest:
              continue
            print(r.full_name)
            res = Resource(repo=r, repo_api=self.repo_api)
            other_r_ver = None
            try:
              other_m_ver = str(res.version)
            except:
              continue
            if hasattr(r.catalog, "prod") and r.catalog.prod:
              other_r_ver = r.catalog.prod.branch_or_tag_name.lstrip('v')
            if not other_m_ver or (not other_r_ver and other_m_ver <= m_ver):
              continue
            if other_r_ver and m_ver <= other_m_ver:
              info[repo.name]['needs_release'] = False
      if info[repo.name]['needs_release']:
        print(f"CREATING RELEASE FOR {info[repo.name]['name']} {info[repo.name]['m_ver']}...")
        info[repo.name]['resource'].create_release()
        print("MADE RELEASE!")
        count += 1
    new_count = 0
    for name in info:
      if info[name]["needs_release"]:
        new_count += 1
    print(f"COUNT: {count}, NEW COUNT {new_count}")


def main():
    if not DCS_TOKEN:
      print("DCS_TOKEN needs to be set as an environment variable.")
      sys.exit(1)
    publisher = Publisher()
    publisher.run()


if __name__ == '__main__':
  main()
