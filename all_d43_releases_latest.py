#!/usr/bin/env python3
#
#  Copyright (c) 2022 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import dcs_api_client
import dcs_catalog_client
from base64 import b64decode
from yaml import safe_load
from os import getenv
from generate_pdf import generate_pdf

if __name__ == '__main__':
    api_config = dcs_catalog_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/catalog"
    v5_api = dcs_catalog_client.V5Api(dcs_catalog_client.ApiClient(api_config))

    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/v1"
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

    resp = v5_api.catalog_search(owner="Door43-Catalog")
    print(len(resp.data))
    for entry in resp.data:
        repo = entry.repo
        release = entry.release
        resp = repo_api.repo_get_single_commit(repo.owner.login, repo.name, 'master')
        master_sha = resp.sha
        resp = repo_api.repo_get_single_commit(repo.owner.login, repo.name, release.tag_name)
        tag_sha = resp.sha
        if master_sha != tag_sha:
            print(f'{repo.name} is different! master: {master_sha}, tag {release.tag_name}: {tag_sha}') 
            try:
                resp2 = repo_api.repo_get_contents(repo=repo.name, owner=repo.owner.login, filepath="manifest.yaml")
            except:
#                print("NO MANIFEST: "+repo.name)
                continue
            manifest = safe_load(b64decode(resp2.content))
            manifest_version = manifest['dublin_core']['version']
            if f'v{manifest_version}' == release.tag_name:
                print("NEED TO DELETE RELEASE/TAG", release.name)
                repo_api.repo_delete_release(repo.owner.login, repo.name, release.id)
                repo_api.repo_delete_tag(repo.owner.login, repo.name, release.tag_name)
            repo_api.repo_create_release(repo.owner.login, repo.name, body=dcs_api_client.CreateReleaseOption(
                tag_name=f'v{manifest_version}', target_commitish='master', name=f"Version {manifest_version}"))
            print(f"Successfully made new release for {repo.name} v{manifest_version}\n\n")
