#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

from distutils.file_util import write_file
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
DCS_DOMAIN = getenv("DCS_DOMAIN", "qa.door43.org")
PUBLISH_DIR = getenv("PUBLISH_DIR", "/tmp/publish")
BOOKS_PUBLISHED = ["rut",  "ezr",  "neh",  "est",  "oba",  "jon",  "luk",  "eph",  "php",  "col",  "1th",  "1ti",  "2ti",  "tit",  "phm",  "jas",  "2pe",  "1jn",  "2jn",  "3jn", "jud"]
RESOURCES = ["uhb", "ugnt", "tw", "twl", "ult", "ust", "ta", "tq", "tn"]
NO_PDF_REPOS = ["uhb", "ugnt", "twl"]
D43_IS_FORK = ["tw", "ult", "ust", "ta", "tn"]
DATE = datetime.now().strftime('%Y-%m-%d')
YEAR = datetime.now().strftime('%Y')

INVERTED_BOOK_NAMES = {v: k for k, v in BOOK_NAMES.items()}

import string
printable = string.ascii_letters + string.digits + string.punctuation + ' '
def hex_escape(s):
    return ''.join(c if c in printable else r'\x{0:02x}'.format(ord(c)) for c in s)


class Resource:

  def __init__(self, name, publisher, dcs="qa.door43.org", working_dir=None, upload=True, debug=False, freeze_only=False):
    self.name = name
    self.publisher = publisher
    self.working_dir = working_dir
    self.dcs = dcs
    self.upload = upload
    self.debug = debug
    self.freeze_only = freeze_only
    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://{dcs}/api/v1"
    self.repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))
    self._repo = None
    self._manifest = None
    self._version = None
    self._prev_version = None
    self._next_version = None
    self._should_publish = None
    self._uw_releases = []
    self._uw_release = None
    self._uw_prs = []
    self._uw_pr = None
    self._d43_prs = []
    self._d43_pr = None
  
  @property
  def repo(self):
    if not self._repo:
      self._repo = self.repo_api.repo_get('unfoldingWord', self.name)
    return self._repo

  @property
  def manifest(self):
    if not self._manifest:
      contents = self.repo_api.repo_get_contents('unfoldingWord', self.name, filepath="manifest.yaml", ref=self.repo.default_branch)
      self._manifest = ruamel.yaml.round_trip_load(b64decode(contents.content), preserve_quotes=True)
    return self._manifest

  @property
  def version(self):
    if not self._version:
      self._version = self.manifest['dublin_core']['version']
    return self._version
  
  @property
  def next_version(self):
    if not self._next_version:
      if not self.should_publish:
        self._next_version = self.version
      else:
        parts = self.version.split('.')
        last = int(parts[-1])
        self._next_version = '.'.join(parts[0:-1] + [str(last + 1)])
    return self._next_version

  @property
  def prev_version(self):
    if not self._prev_version:
      parts = self.version.split('.')
      last = int(parts[-1])
      self._prev_version = '.'.join(parts[0:-1] + [str(last - 1)])
    return self._prev_version

  @property
  def should_publish(self):
    if not self._should_publish:
      master_branch = self.repo_api.repo_get_branch('unfoldingWord', self.name, self.repo.default_branch)
      last_tag = self.repo_api.repo_get_tag('unfoldingWord', self.name, f'v{self.version}')
      if last_tag.id == master_branch.commit.id:
        self._should_publish = False
      else:
        self._should_publish = True
    return self._should_publish
  
  @property
  def prepub_branch_name(self):
    return f"prePub{self.next_version}"

  @property
  def uw_release(self):
    if not self._uw_release:
      releases = self.repo_api.repo_list_releases('unfoldingWord', self.name)
      for release in releases:
        if release.tag_name == f"v{self.next_version}":
          self._uw_release = release
          break
    return self._uw_release

  @property
  def uw_prs(self):
    if not self._uw_prs:
      self._uw_prs = self.repo_api.repo_list_pull_requests('unfoldingWord', self.name, state='open')
    return self._uw_prs
  
  @property
  def uw_pr(self):
    if not self._uw_pr:
      for pr in self.uw_prs:
        if pr.head.label == self.prepub_branch_name:
          self._uw_pr = pr
          break
    return self._uw_pr

  @property
  def d43_prs(self):
    if not self._d43_prs:
      self._d43_prs = self.repo_api.repo_list_pull_requests('Door43-Catalog', self.name, state='open')
    return self._d43_prs
  
  @property
  def d43_pr(self):
    if not self._d43_pr:
      for pr in self.d43_prs:
        if pr.head.label == self.prepub_branch_name:
          self._d43_pr = pr
          break
    return self._d43_pr

  def publish(self):
    if not self.should_publish:
      print(f"No need to publish unfoldingWord/{self.name} so not making any new branches/releeases/PRs for it.")
      return
    self.publish_to_uw()
    self.publish_to_d43()

  def publish_to_uw(self):
    self.make_uw_prepub_branch()
    if self.freeze_only:
      print(f"Only freezing the uW master branch as {self.prepub_branch_name}. Ending here.")
      return
    self.update_uw_files()
    self.make_uw_release()
    self.make_uw_pr()

  def publish_to_d43(self):
    self.make_d43_prepub_branch()
    self.make_d43_pr()

  def make_uw_prepub_branch(self):
    try:
      self.branch = self.repo_api.repo_get_branch('unfoldingWord', self.name, self.prepub_branch_name)
      print(f"Branch {self.prepub_branch_name} for unfoldingWord/{self.name} already exists")
    except ApiException:
      self.branch = self.repo_api.repo_create_branch('unfoldingWord', self.name, body=dcs_api_client.CreateBranchRepoOption(old_branch_name=self.repo.default_branch, new_branch_name=self.prepub_branch_name))
      print(f"Created branch for unfoldingWord/{self.name} as {self.prepub_branch_name}")
  
  def update_uw_files(self):
    self.update_uw_manifest()
    self.update_uw_license()

  def update_uw_manifest(self):
    orig_manifest_contents = self.repo_api.repo_get_contents('unfoldingWord', self.name, filepath="manifest.yaml", ref=self.prepub_branch_name)
    orig_manifest_str = b64decode(orig_manifest_contents.content).decode('utf-8')
    new_manifest = ruamel.yaml.round_trip_load(orig_manifest_str, preserve_quotes=True)
    new_manifest['dublin_core']['modified'] = new_manifest['dublin_core']['issued'] = datetime.now().strftime('%Y-%m-%d')
    new_manifest['dublin_core']['version'] = self.next_version
    for idx, source in enumerate(new_manifest['dublin_core']['source']):
      if source['identifier'] == self.manifest['dublin_core']['identifier'] and source['language'] == self.manifest['dublin_core']['language']:
        new_manifest['dublin_core']['source'][idx]['version'] = self.prev_version
    for idx, relation in enumerate(new_manifest['dublin_core']['relation']):
      lang, rest = relation.split('/')
      if '?' in rest:
        resource, rest = rest.split('?')
      else:
        resource = rest
      repo_name = f"{lang}_{resource}"
      if repo_name in self.publisher.resources:
        new_manifest['dublin_core']['relation'][idx] = f"{lang}/{resource}?v={self.publisher.resources[repo_name].next_version}"
    for idx, source in enumerate(new_manifest['dublin_core']['source']):
      repo_name = f'{source["language"]}_{source["identifier"]}'
      if repo_name in self.publisher.resources:
        if repo_name == self.name:
          new_manifest['dublin_core']['source'][idx]['version'] = self.publisher.resources[repo_name].version
        else:
          new_manifest['dublin_core']['source'][idx]['version'] = self.publisher.resources[repo_name].next_version          
    new_manifest_str = ruamel.yaml.round_trip_dump(new_manifest, explicit_start=True, width=4096)
    if orig_manifest_str != new_manifest_str:
      manifest_contents = self.repo_api.repo_get_contents('unfoldingWord', self.name, filepath="manifest.yaml", ref=self.prepub_branch_name)
      body = dcs_api_client.UpdateFileOptions(
        branch=self.prepub_branch_name,
        sha=manifest_contents.sha,
        content=b64encode(new_manifest_str.encode('utf-8')).decode('utf-8'),
        message=f'Version {self.next_version}'
      )
      self.repo_api.repo_update_file('unfoldingWord', self.name, 'manifest.yaml', body)

  def update_uw_license(self):
    license_contents = self.repo_api.repo_get_contents('unfoldingWord', self.name, filepath="LICENSE.md", ref=self.prepub_branch_name)
    orig_license = b64decode(license_contents.content).decode('utf-8')
    new_license = re.sub('© 20[0-9][0-9] by unfoldingWord', f'© {datetime.now().strftime("%Y")} by unfoldingWord', orig_license)  
    if orig_license != new_license:
      body = dcs_api_client.UpdateFileOptions(branch=self.prepub_branch_name, sha=license_contents.sha, content=b64encode(new_license.encode('utf-8')).decode('utf-8'))
      self.repo_api.repo_update_file('unfoldingWord', self.name, 'LICENSE.md', body)
  
  def make_uw_release(self):
    if self.uw_release:
      try:
        self.repo_api.repo_delete_release('unfoldingWord', self.name, self.uw_release.id)
        self._uw_release = None
      except ApiException:
        print("Unable to delete release")
        sys.exit(1)

    if self.uw_release:
      print("Release is not deleted!")
      sys.exit(1)

    try:
      self.repo_api.repo_delete_tag('unfoldingWord', self.name, f'v{self.next_version}')
    except ApiException:
      pass
    self.repo_api.repo_create_tag('unfoldingWord', self.name, body=dcs_api_client.CreateTagOption(tag_name=f'v{self.next_version}', target=self.prepub_branch_name))  

    body = dcs_api_client.CreateReleaseOption(
      name=f'Version {self.next_version}',
      tag_name=f'v{self.next_version}',
      prerelease=False,
      draft=False,
      target_commitish="master",
      body=self.generate_release_notes()
    )
    resp = self.repo_api.repo_create_release('unfoldingWord', self.name, body=body)
    self._uw_release = None
    if not resp:
      print(f"FAILED TO CREATE/UPDATE RELEASE FOR unfoldingWord/{self.name}")
      sys.exit(1)

  def generate_release_notes(self):
    release_body = ''
    if not self.uw_release or '* ' not in self.uw_release.body:
      releases = self.repo_api.repo_list_releases('unfoldingWord', self.name)
      for release in releases:
        if '* ' in release.body:
          release_body = release.body
          break
    if not release_body or '* ' not in release_body:
      print(f"{self.name} needs a release with a body containing the books!")
      sys.exit(1)
    bullets_started = bullets_ended = False
    existing_books = []
    before_books = []
    after_books = []
    release_body = release_body.replace('\x0d\x0a', '\n')
    for line in release_body.split('\n'):
      if line.startswith('* ') and not bullets_ended:
        bullets_started = True
        match = re.match('^\* +(.+?)( *\(.*\) *)*$', line)
        if match:
          book_name = match[1]
          if book_name in INVERTED_BOOK_NAMES:
            existing_books.append(INVERTED_BOOK_NAMES[book_name])
      elif bullets_started or bullets_ended:
        bullets_ended = True
        after_books.append(line)
      else:
        before_books.append(line)
    release_body = '\n'.join(before_books) + '\n'
    for book_id in BOOK_NAMES:
      if book_id in existing_books or book_id in self.publisher.book_ids:
        release_body += f'* {BOOK_NAMES[book_id]} ({book_id.upper()})\n'
    release_body += '\n'.join(after_books) + '\n'
    books = []
    for book_id in self.publisher.book_ids:
      books.append(f'{BOOK_NAMES[book_id]} ({book_id.upper()})')
    release_body = re.sub(r'version [\d\.]+', f'version {self.next_version}', release_body)
    release_body = re.sub("Book Packages complete: (.*)\n", f"Book Packages complete: {', '.join(books)}\n", release_body)
    release_body = re.sub(r'v[\d\.]+(\.\.+)v[\d\.]+', f'v{self.version}...v{self.next_version}', release_body)
    release_body = re.sub(fr'{self.name}/v[\d\.]+', f'{self.name}/v{self.next_version}', release_body)
    return release_body

  def make_uw_pr(self):
    if not self.uw_pr:
      body = dcs_api_client.CreatePullRequestOption(
        title=f'Version {self.next_version}',
        head=self.prepub_branch_name,
        base=self.repo.default_branch,
        body=self.generate_release_notes()
      )
      resp = self.repo_api.repo_create_pull_request('unfoldingWord', self.name, body=body)
    else:
      body = dcs_api_client.EditPullRequestOption(
        title=f'Version {self.next_version}',
        body=self.generate_release_notes()
      )
      resp = self.repo_api.repo_edit_pull_request('unfoldingWord', self.name, self.uw_pr.number, body=body)
    if not resp:
      print(f"FAILED TO CREATE/UPDATE PULL REQUEST FOR {self.name}")
      sys.exit(1)    

  def make_d43_prepub_branch(self):
    try:
      self.repo_api.repo_delete_branch('Door43-Catalog', self.name, self.prepub_branch_name)
    except ApiException:
      pass
    tmp_path = '/tmp/publish'
    os.makedirs(tmp_path, exist_ok=True)
    repo_path = os.path.join(tmp_path, self.name)
    shutil.rmtree(repo_path, ignore_errors=True)    
    repo = Repo.clone_from(f'git@{self.dcs}:unfoldingWord/{self.name}.git', repo_path, branch=self.prepub_branch_name)
    repo.git.push(f'git@{self.dcs}:Door43-Catalog/{self.name}.git')

  def make_d43_pr(self):
    if not self.d43_pr:
      body = dcs_api_client.CreatePullRequestOption(
        title=f'Version {self.next_version}',
        head=self.prepub_branch_name,
        base=self.repo.default_branch,
        body=self.generate_release_notes()
      )
      resp = self.repo_api.repo_create_pull_request('Door43-Catalog', self.name, body=body)
    else:
      body = dcs_api_client.EditPullRequestOption(
        title=f'Version {self.next_version}',
        body=self.generate_release_notes()
      )
      resp = self.repo_api.repo_edit_pull_request('Door43-Catalog', self.name, self.uw_pr.number, body=body)
    if not resp:
      print(f"FAILED TO CREATE/UPDATE PULL REQUEST FOR Door43-Cagtalog/{self.name}")
      sys.exit(1)    

  def generate_pdf(self):
    pdf_path = output_file=f'/tmp/pdfs/{self.name}'
    if not os.path.exists(pdf_path):
      generate_pdf(repo_name=self.name, output_file=pdf_path)


class BibleResource(Resource):
  
  def make_d43_prepub_branch(self):
    try:
      self.repo_api.repo_delete_branch('Door43-Catalog', self.name, self.prepub_branch_name)
    except ApiException:
      pass
    tmp_path = '/tmp/publish'
    os.makedirs(tmp_path, exist_ok=True)
    repo_path = os.path.join(tmp_path, self.name)
    shutil.rmtree(repo_path, ignore_errors=True)    
    repo = Repo.clone_from(f'git@{self.dcs}:unfoldingWord/{self.name}.git', repo_path, branch=self.prepub_branch_name)
    manifest_path = os.path.join(repo_path, 'manifest.yaml')
    manifest = {}
    with open(manifest_path) as manifest_fp:
      manifest = ruamel.yaml.round_trip_load(manifest_fp, preserve_quotes=True)
    projects = []
    for project in manifest['projects']:
      if project['identifier'] not in ['frt', 'bak']:
        projects.append(project)
    manifest['projects'] = projects
    manifest_dump = ruamel.yaml.round_trip_dump(manifest, explicit_start=True, width=4096)
    with open(manifest_path, "w") as manifest_fp:
      manifest_fp.write(manifest_dump)
    repo.git.add('*')
    repo.git.commit(m=f'Version {self.next_version}')
    repo.git.push(f'git@{self.dcs}:Door43-Catalog/{self.name}.git')


class TWLResource(Resource):
  
  def publish_to_d43(self):
    # WE DO NOT PUBLISH THIS RESOURCE TO D43
    pass

  def generate_pdf(self):
    # WE DO NOT GENERATE PDFS FOR THIS RESOURCE
    pass

class OLResource(Resource):
  
  def make_d43_prepub_branch(self):
    tmp_path = '/tmp/publish'
    os.makedirs(tmp_path, exist_ok=True)
    ol_path = os.path.join(tmp_path, self.name)
    twl_path = os.path.join(tmp_path, 'en_twl')
    shutil.rmtree(ol_path, ignore_errors=True)
    shutil.rmtree(twl_path, ignore_errors=True)
    
    repo = Repo.clone_from(f'git@{self.dcs}:Door43-Catalog/{self.name}.git', ol_path) #, filter=['tree:0','blob:none'], sparse=True)

    for b in repo.remote().refs:
      if b.name == f'{repo.remote().name}/{self.prepub_branch_name}':
        repo.remote().push(refspec=(":%s" % b.remote_head))
    branch = repo.create_head(self.prepub_branch_name)
    branch.checkout()
    
    upstream = repo.create_remote(f'upstream', f'git@{self.dcs}:unfoldingWord/{self.name}.git')
    upstream.fetch(self.prepub_branch_name, filter=['tree:0','blob:none'])
    repo.git.checkout(f'upstream/{self.prepub_branch_name}', '*.usfm', '*.md', '*.yaml')

    Repo.clone_from(f'git@{self.dcs}:unfoldingWord/en_twl.git', twl_path, 
      branch=self.publisher.resources['en_twl'].prepub_branch_name,
      filter=['tree:0','blob:none'], sparse=True)
    insert_twl_into_ol(ol_path, twl_path)    
    repo.git.add('*')
    repo.git.commit(m=f'Version {self.next_version}')
    repo.git.push('--set-upstream', 'origin', branch)

  def generate_pdf(self):
    pass


class TQResource(Resource):

  def make_d43_prepub_branch(self):
    tmp_path = '/tmp/publish'
    os.makedirs(tmp_path, exist_ok=True)
    tsv_path = os.path.join(tmp_path, f'{self.name}_tsv')
    md_path = os.path.join(tmp_path, f'{self.name}_md')
    shutil.rmtree(tsv_path, ignore_errors=True)
    shutil.rmtree(md_path, ignore_errors=True)

    Repo.clone_from(f'git@{self.dcs}:unfoldingWord/{self.name}.git', tsv_path, branch=self.prepub_branch_name)    

    repo = Repo.clone_from(f'git@{self.dcs}:Door43-Catalog/{self.name}.git', md_path) #, filter=['tree:0','blob:none'], sparse=True)
    upstream = repo.create_remote(f'upstream', f'git@{self.dcs}:unfoldingWord/{self.name}.git')
    upstream.fetch(self.prepub_branch_name, filter=['tree:0','blob:none'])

    for b in repo.remote().refs:
      if b.name == f'{repo.remote().name}/{self.prepub_branch_name}':
        repo.remote().push(refspec=(":%s" % b.remote_head))
    branch = repo.create_head(self.prepub_branch_name)
    branch.checkout()
    
    repo.git.checkout(f'upstream/{self.prepub_branch_name}', '*.md', '*.yaml')

    convert_tsv_tq_to_md_tq(tsv_path, md_path)    
    repo.git.add('*')
    repo.git.commit(m=f'Version {self.next_version}')
    repo.git.push('--set-upstream', 'origin', branch)


class Publisher:

  def __init__(self, book_ids, working_dir=None, dcs='qa.door43.org', upload=True, debug=False):
    self.dcs = dcs
    self.upload = upload
    self.debug = debug
    self.book_ids = book_ids
    self.resources = None

    self.working_dir = working_dir
    if not working_dir:
      self.temp_dir = tempfile.mkdtemp(prefix='publisher')
    else:
      self.temp_dir = working_dir
    
    if not os.path.exists(self.temp_dir):
      os.makedirs(self.temp_dir)

  def __del__(self):
    if not self.working_dir and not self.debug:
      shutil.rmtree(self.temp_dir)

  def run(self):
    self.resources = OrderedDict({
      'en_twl': TWLResource(name='en_twl', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_tw': Resource(name='en_tw', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'el-x-koine_ugnt': OLResource(name='el-x-koine_ugnt', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'hbo_uhb': OLResource(name='hbo_uhb', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_ult': BibleResource(name='en_ult', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_ust': BibleResource(name='en_ust', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_ta': Resource(name='en_ta', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_tq': TQResource(name='en_tq', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
      'en_tn': Resource(name='en_tn', publisher=self, dcs=self.dcs, working_dir=self.working_dir, upload=self.upload, debug=self.debug),
    })

    # for resource in self.resources.values():
    #   resource.publish()
    for resource in self.resources.values():
      resource.generate_pdf()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-w', '--working_dir', dest='working_dir', required=False,
                        help='Path to the working dir. Default: a temp directory')
    parser.add_argument('--no-upload', dest='upload', action='store_false', help="Do NOT upload files to the S3 CDN")
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help="Debug mode. Default: false")
    parser.add_argument('--dcs', dest='dcs', default=DCS_DOMAIN, help=f'DCS domain name. Default: {DCS_DOMAIN}')
    parser.add_argument('-b', '--book', metavar='BOOK ID', dest='book_ids', required=True, action='append',
                        help='Book ID of the book(s) being published this release')

    args = parser.parse_args(sys.argv[1:])

    upload = args.upload
    debug = args.debug
    dcs = args.dcs
    book_ids = args.book_ids

    for book_id in book_ids:
      if book_id not in BOOK_NAMES:
        print(f"Invalid Book ID: {book_id}")
        sys.exit(1)

    working_dir = args.working_dir

    if not AWS_ACCESS_KEY_ID:
      print("AWS_ACCESS_KEY_ID needs to be set as an environment variable.")
      sys.exit(1)
    if not AWS_SECRET_ACCESS_KEY:
      print("AWS_SECRET_ACCESS_KEY needs to be set as an environment variable.")
      sys.exit(1)
    if not DCS_TOKEN:
      print("DCS_TOKEN needs to be set as an environment variable.")
      sys.exit(1)

    print(f"DCS: {dcs}")

    publisher = Publisher(book_ids=book_ids, working_dir=working_dir, dcs=dcs, upload=upload, debug=debug)
    publisher.run()
    exit(1)


if __name__ == '__main__':
  main()
