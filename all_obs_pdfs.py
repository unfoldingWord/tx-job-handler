#!/usr/bin/env python3
#
#  Copyright (c) 2022 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import sys
import dcs_api_client
from base64 import b64decode
from yaml import safe_load
from os import getenv

if __name__ == '__main__':
    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/v1"
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))
    resp = repo_api.repo_search(subject="Door43-Catalog")
    for repo in resp.data:
        if not repo.parent:
            repo = repo_api.repo_get(repo=repo.name, owner=repo.owner.login)
            if repo.archived:
#                print("ARCHIVE: "+repo.name)
                continue
            print(f"REPO: {repo.name}")
            try:
                resp2 = repo_api.repo_get_contents(repo=repo.name, owner=repo.owner.login, filepath="manifest.yaml")
            except:
#                print("NO MANIFEST: "+repo.name)
                continue
            if not repo.catalog or not repo.catalog.latest:
                print("NO LATEST: "+repo.name)
                sys.exit(1)
            manifest = safe_load(b64decode(resp2.content))
            manifest_version = manifest['dublin_core']['version']
            if not repo.catalog or not repo.catalog.prod or repo.catalog.prod.branch_or_tag_name != f"v{manifest_version}":
                print(repo.name, manifest_version)
                body = {"name": f"Version {manifest_version}", "tag_name": f"v{manifest_version}", "prerelease": False, "draft": False, "target_commitish": "master"}
                print(body)
                resp3 = repo_api.repo_create_release(repo.owner.login, repo.name, body=body)
                repo = repo_api.repo_get(repo=repo.name, owner=repo.owner.login)
