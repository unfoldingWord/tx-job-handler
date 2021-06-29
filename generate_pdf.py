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
from webhook import process_tx_job
from door43_tools.subjects import SUBJECT_ALIASES


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--output_file', dest='output_file', required=False,
                        help='Path to output file, including the zip file name')
    parser.add_argument('--owner', dest='owner', default="unfoldingWord", required=False,
                        help=f'Owner of the resource repo on GitHub. Default: unfoldingWord')
    parser.add_argument('--repo', dest='repo_name', required=True, help=f'Repo name')
    parser.add_argument('--ref', dest='ref', default='master', help='Branch or tag name. Default: master')
    parser.add_argument('-p', '--project_id', metavar='PROJECT ID', dest='project_ids', required=False, action='append',
                        help='Project ID for resources with projects, as listed in the manfiest.yaml file, such as a Bible book '+
                        '(-p gen). Can specify multiple projects. Default: None (different converters will handle no or multiple '+
                        'projects differently, such as compiling all into one PDF, or generating a PDF for each project)')

    args = parser.parse_args(sys.argv[1:])

    lang, resource = args.repo_name.split('_')
    subject = None
    for s, r in SUBJECT_ALIASES.items():
      if resource == r[0]:
        subject = s.replace(' ', '_')
        break
    input_format = "md"
    if subject.startswith('TSV'):
      input_format = "tsv"

    data = {
      "output": args.output_file,
      "job_id": f"Door43--{args.owner}--{args.repo_name}",
      "identifier": f"{args.owner}--{args.repo_name}",
      "resource_type": subject,
      "input_format": input_format,
      "output_format": "pdf",
      "source": f"https://git.door43.org/{args.owner}/{args.repo_name}/archive/{args.ref}.zip",
      "repo_name": args.repo_name,
      "repo_owner": args.owner,
      "repo_ref": args.ref,
      "repo_data_url": f"https://git.door43.org/{args.owner}/{args.repo_name}/archive/{args.ref}.zip",
      "dcs_domain": "https://git.door43.org",
      "project_ids": args.project_ids,
    }
    print(data)
    process_tx_job("dev", data)
