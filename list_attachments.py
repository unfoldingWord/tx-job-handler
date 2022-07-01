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
import dcs_catalog_client
from base64 import b64decode
from yaml import safe_load
from os import getenv
from generate_pdf import generate_pdf

if __name__ == '__main__':
    # api_config = dcs_api_client.Configuration()
    # api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    # api_config.host = f"https://git.door43.org/api/v1"
    # repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

    api_config = dcs_catalog_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/catalog"
    v5_api = dcs_catalog_client.V5Api(dcs_catalog_client.ApiClient(api_config))

    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/v1"
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

    resp = v5_api.catalog_search(owner="Door43-Catalog", repo='nag_ta')
    print(len(resp.data))
    for entry in resp.data:
        # if entry.repo.name != 'ne_obs-tn':
        #     continue
        # if not len(entry.release.assets) > 0 and ('Open' in entry.repo.subject or 'OBS' in entry.repo.subject):            
        #     print(entry.repo.name, entry.repo.owner.login, entry.release.name)
        #     try:
        #         generate_pdf(owner=entry.repo.owner.login, repo_name=entry.repo.name, dcs_domain='git.door43.org')
        #     except Exception as e:
        #         print("ERROR!!!!!!!! UNABLE TO PPROCESS!", entry.repo.name, entry.repo.owner.login, entry.release.name)
        #         print(e)
        # if len(entry.release.assets) <= 0:
        #     print(f"===========\nName:{entry.repo.full_name}:")
        #     for asset in entry.release.assets:
        #         if asset.name.endswith('.pdf'):
        #             print(f"  ==> {asset.name}")
        resp = repo_api.repo_get_single_commit(entry.repo.owner.login, entry.repo.name, 'master')
        master_sha = resp.sha
        print(master_sha)
        resp = repo_api.repo_get_single_commit(entry.repo.owner.login, entry.repo.name, entry.release.tag_name)
        print(resp.sha)
        exit(1)
