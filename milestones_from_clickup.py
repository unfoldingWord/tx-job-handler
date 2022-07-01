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
import dcs_api_client
import shutil
import argparse
import re
import requests
from collections import OrderedDict
from pprint import pprint
from os import getenv
from datetime import datetime
from dcs_api_client.rest import ApiException 
from door43_tools.bible_books import BOOK_NAMES

DCS_TOKEN = getenv("DCS_TOKEN")
DCS_DOMAIN = getenv("DCS_DOMAIN", "qa.door43.org")
CLICKUP_TOKEN = getenv("CLICKUP_TOKEN")
RESOURCES = ["uhb", "ugnt", "tw", "twl", "ult", "ust", "ta", "tq", "tn"]

INVERTED_BOOK_NAMES = {v.lower(): k for k, v in BOOK_NAMES.items()}


class Milestones:

  def __init__(self, dcs='qa.door43.org', debug=False):
    self.dcs = dcs
    self.debug = debug
    self.resources = None

  def run(self):
    headers = {"Authorization": CLICKUP_TOKEN}
    books_done = {'en': []}
    # r = requests.request(method="GET", url="https://api.clickup.com/api/v2/team/8466374/task?space=10664140&statuses%5B%5D=bp%20complete&statuses%5B%5D=gl%20ready", headers=headers)
    # tasks = r.json()['tasks']
    # for task in tasks:
    #   name = task['name'].split(':')[-1].strip(' ')
    #   print(name)
    #   if name == 'OBS':
    #     code = 'obs'
    #   else:
    #     code = INVERTED_BOOK_NAMES[name.lower()]      
    #   books_done['en'].append(code)
    #   print(code)

    r = requests.request(method="GET", url="https://api.clickup.com/api/v2/team/8466374/task?space=14782142&statuses%5B%5D=publish%20to%20dcs&statuses%5B%5D=test%20bp%20with%20ol&statuses%5B%5D=bp%20ready%20for%20ol&statuses%5B%5D=ol%20using%20bp&statuses%5B%5D=ol%20engaging%20church", headers=headers)
    tasks = r.json()['tasks']
    for task in tasks:
      info = task['name'].split(': ', 1)[-1].strip()
      print(info)
      name, lang = info.split('(', 1)
      name = name.strip()
      lang = lang.split(': ')[-1].strip(')')
      if name == 'OBS':
        code = 'obs'
      else:
        code = INVERTED_BOOK_NAMES[name.lower()]
      print(code, lang)
      # if name == 'OBS':
      #   code = 'obs'
      # else:
      #   code = INVERTED_BOOK_NAMES[name.lower()]      
      # print(code)

    # curl --header "Authorization: $CLICKUP_TOKEN" 'https://api.clickup.com/api/v2/team/8466374/task?space=10664140&statuses%5B%5D=bp%20complete&statuses%5B%5D=gl%20ready' | jq '[ .tasks[] | {id: .id, name: .name, due_date: .due_date | (.|tonumber / 1000 | strftime("%Y-%m-%d")), created: .date_created | (.|tonumber / 1000 | strftime("%Y-%m-%d")), updated: .date_updated | (.|tonumber / 1000 | strftime("%Y-%m-%d")), status: .status.status, tags: [.tags[].name]}]'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help="Debug mode. Default: false")
    parser.add_argument('--dcs', dest='dcs', default=DCS_DOMAIN, help=f'DCS domain name. Default: {DCS_DOMAIN}')

    args = parser.parse_args(sys.argv[1:])

    debug = args.debug
    dcs = args.dcs

    if not DCS_TOKEN:
      print("DCS_TOKEN needs to be set as an environment variable.")
      sys.exit(1)

    if not CLICKUP_TOKEN:
      print("CLICKUP_TOKEN needs to be set as an environment variable.")
      sys.exit(1)

    print(f"DCS: {dcs}")

    milestones = Milestones(dcs=dcs, debug=debug)
    milestones.run()
    exit(1)


if __name__ == '__main__':
  main()
