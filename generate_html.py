#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import argparse
import sys
import os
import shutil
import boto3
import dcs_api_client
from webhook import process_tx_job
from door43_tools.subjects import SUBJECT_ALIASES
from door43_tools.bible_books import BOOK_NAMES
from glob import glob
from botocore.exceptions import ClientError


def generate_html(repo_name, owner='unfoldingWord', ref=None, dcs_domain='git.door43.org', input_format=None, project_ids=[], output_file=None, subject=None):
    if not owner or owner == "unfoldingword":
        owner = "unfoldingWord"
    if owner == "door43-catalog":
        owner = "Door43-Catalog"

    if '_' in repo_name:
        lang, resource, *_ = repo_name.lower().split('_')
    else:
        lang = 'en'
        resource = repo_name.lower()

    if resource == 'bhp':
        lang = 'el-x-koine'

    for s, aliases in SUBJECT_ALIASES.items():
        for alias in aliases:
            if resource == alias:
                subject = s
                break
        else:
            continue
        break

    if subject:
        subject = subject.replace(' ', '_')

    if not input_format:
        if subject:
            if subject.startswith('TSV'):
                input_format = "tsv"
            elif subject.replace(' ', '_') in ['Aligned_Bible', 'Bible', 'Greek_New_Testament', 'Hebrew_Old_Testament']:
                input_format = "usfm"
            else:
                input_format = "md"
        else:
            input_format = "md"
 
    if project_ids:
        (map(lambda x: x.lower(), project_ids))
    else:
        project_ids = []

    api_config = dcs_api_client.Configuration()
    api_config.host = f"{dcs_domain}/api/v1"
    api_config.api_key['access_token'] = os.getenv('DCS_TOKEN')
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))
    release = None
    releases = repo_api.repo_list_releases(owner, repo_name)
    if not ref:
        if len(releases):
            release = releases[0]
            ref = release.tag_name
        else:
            ref = 'master'
    elif ref != 'master':
        for r in releases:
            if r.tag_name == ref:
                release = r

    output_file = output_file
    if not output_file:
        output_file = os.path.join("/tmp", f"{repo_name}_{ref}")
    if not output_file.endswith(".zip"):
        output_file = os.path.join(output_file, f"{repo_name}_{ref}.zip")
    # if os.path.exists(output_file):
    #     if input(f"Are you sure you want to overwrite {output_file}? (y/n)") != "y":
    #         return

    orig_pdf_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.pdf')))

    if len(orig_pdf_files) < 1 or (len(orig_pdf_files) > 2 and len(orig_pdf_files) != 67):
        data = {
            "output": output_file,
            "job_id": f"Door43--{owner}--{repo_name}",
            "identifier": f"{owner}--{repo_name}",
            "resource_type": subject,
            "input_format": input_format,
            "output_format": "html",
            "source": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "repo_name": repo_name,
            "repo_owner": owner,
            "repo_ref": ref,
            "repo_data_url": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "dcs_domain": f"https://{dcs_domain}",
            "project_ids": project_ids,
        }
    
        print(data)
        process_tx_job("dev", data)
        print("Done!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--output_file', dest='output_file', required=False,
                        help='Path to output file, including the zip file name')
    parser.add_argument('--owner', dest='owner', default="unfoldingWord", required=False,
                        help='Owner of the resource repo on GitHub. Default: unfoldingWord')
    parser.add_argument('--repo', dest='repo_name', required=True, help='Repo name')
    parser.add_argument('--ref', dest='ref', required=False, help='Branch or tag name. Default: latest release or master')
    parser.add_argument('--input', dest='input_format', required=False, help='Input type. Default: md')
    parser.add_argument('-p', '--project_id', metavar='PROJECT ID', dest='project_ids', required=False, action='append',
                        help='Project ID for resources with projects, as listed in the manfiest.yaml file, such as a Bible book ' +
                        '(-p gen). Can specify multiple projects. Default: None (different converters will handle no or multiple ' +
                        'projects differently, such as compiling all into one PDF, or generating a PDF for each project)')
    parser.add_argument('--dcs-domain', dest='dcs_domain', default='git.door43.org', help='DCS domain name. Default: git.door43.org')

    args = parser.parse_args(sys.argv[1:])
    generate_html(**vars(args))
