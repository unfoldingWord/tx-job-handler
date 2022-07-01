#!/usr/bin/env python3
#
#  Copyright (c) 2022 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import os
import dcs_api_client
import dcs_catalog_client
from base64 import b64decode
from yaml import safe_load
from os import getenv
from generate_pdf import generate_pdf

if __name__ == '__main__':
    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/v1"
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

    api_config = dcs_catalog_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/catalog"
    v5_api = dcs_catalog_client.V5Api(dcs_catalog_client.ApiClient(api_config))

    resp = v5_api.catalog_search(subject='Open Bible Stories')
    print(len(resp.data))
    for entry in resp.data:
        repo = entry.repo
        try:
            resp = repo_api.repo_get_contents(repo=repo.name, owner=repo.owner.login, filepath="manifest.yaml")
        except:
            continue
        manifest = safe_load(b64decode(resp.content))
        manifest_version = manifest['dublin_core']['version']
        release_version = entry.release.tag_name.lstrip('v')
        try:
            resp = repo_api.repo_get_contents(repo=repo.name, owner=repo.owner.login, filepath="media.yaml")
        except:
            print(f"NO MEDIA FILE FOR {repo.owner.login}/{repo.name}")
            continue
        media = safe_load(b64decode(resp.content))
        project = media['projects'][0]
        media_version = project['version']
        for m in project['media']:
            url = m['url']
            url = url.replace('{latest}', manifest_version)
            name = os.path.basename(url)
            print(url)

            