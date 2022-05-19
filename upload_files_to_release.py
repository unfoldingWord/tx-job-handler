#!/usr/bin/env python3
#
#  Copyright (c) 2022 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import dcs_api_client
import os
from os import getenv
from glob import glob

if __name__ == '__main__':
    api_config = dcs_api_client.Configuration()
    api_config.api_key['access_token'] = getenv('DCS_TOKEN')
    api_config.host = f"https://git.door43.org/api/v1"
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))

    release = repo_api.repo_get_release_by_tag('unfoldingWord', 'en_obs', 'v6')
    dirs = ['128kbps', '64kbps', '32kbps', 'docx', 'epub', 'odt']
    for dir in dirs:
        files = glob(os.path.join('/tmp/v6', dir, '*'))
        for file in sorted(files):
            name = os.path.basename(file)
            if not name.startswith('en_obs_v'):
                name = name.replace('en_obs_', 'en_obs_v6_')
            print(f"{file} ===> {name}")
            repo_api.repo_create_release_attachment('unfoldingWord', 'en_obs', release.id, file, name=name)
            exit(1)
