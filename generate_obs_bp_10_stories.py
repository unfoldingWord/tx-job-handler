#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import sys
import os
import dcs_api_client
from webhook import process_tx_job
from glob import glob
from botocore.exceptions import ClientError


def generate_pdf():
    dcs_domain = "git.door43.org"
    owner = "unfoldingWord"
    repo_name = "en_obs-tn"
    api_config = dcs_api_client.Configuration()
    api_config.host = f"https://{dcs_domain}/api/v1"
    api_config.api_key['access_token'] = os.getenv('DCS_TOKEN')
    ref = "master"
    output_file = "/tmp/obs_bp/out.zip"
    # orig_pdf_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.pdf')))
    orig_pdf_files = []

    if len(orig_pdf_files) < 1 or (len(orig_pdf_files) > 2 and len(orig_pdf_files) != 67):
        data = {
            "output": output_file,
            "job_id": f"Door43--{owner}--{repo_name}",
            "identifier": f"{owner}--{repo_name}",
            "resource_type": "OBS BP 10 STORIES",
            "input_format": "md",
            "output_format": "pdf",
            "source": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "repo_name": repo_name,
            "repo_owner": owner,
            "repo_ref": ref,
            "repo_data_url": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "dcs_domain": f"https://{dcs_domain}",
            "project_ids": "obs",
        }

        print(data)
        process_tx_job("dev", data)

        orig_pdf_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.pdf')))

    if len(orig_pdf_files) < 1:
        print("NO PDF FILES WERE GENERATED!!!")
        sys.exit(1)

    print("PDF files were generated.")


if __name__ == '__main__':
    generate_pdf()
