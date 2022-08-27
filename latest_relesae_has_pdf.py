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

    if len(sys.argv) > 1:
        resp = v5_api.catalog_search(subject=','.join(sys.argv[1:]))
    else:
        resp = v5_api.catalog_search()
    print(len(resp.data))
    for entry in resp.data:
        repo = entry.repo
        if not len(entry.release.assets) > 0:            
            print(entry.repo.name, entry.repo.owner.login, entry.release.name)
            print(repo.subject)
            generate_pdf(owner=entry.repo.owner.login, repo_name=entry.repo.name, dcs_domain='git.door43.org', subject=repo.subject)
            # try:
            # except Exception as e:
            #     print("ERROR!!!!!!!! UNABLE TO PPROCESS!", entry.repo.name, entry.repo.owner.login, entry.release.name)
            #     print(e)
