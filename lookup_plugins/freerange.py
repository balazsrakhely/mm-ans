#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2020, Men&Mice
# GNU General Public License v3.0
# see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt
#
# python 3 headers, required if submitting to Ansible
"""Ansible lookup plugin.

Lookup plugin for finding the next matching range in
a network zone in the Micetro.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible.errors import AnsibleError, AnsibleModuleError
from ansible.module_utils.common.text.converters import to_text
from ansible.plugins.lookup import LookupBase
from ansible_collections.menandmice.ansible_micetro.plugins.module_utils.micetro import (
    doapi,
    TRUEFALSE,
)

DOCUMENTATION = r"""
    lookup: freerange
    short_description: Find the first matching network range
    options:
      mm_provider:
        description: Definition of the Micetro API mm_provider
        type: dict
        required: True
        suboptions:
          mm_url:
            description: Men&Mice API server to connect to
            required: True
            type: str
          mm_user:
            description: userid to login with into the API
            required: True
            type: str
          mm_password:
            description: password to login with into the API
            required: True
            type: str
            no_log: True
      network:
        description:
          - network zone(s) from which the first matching subnet is to be found
          - This is either a single network or a list of networks
        type: list
        required: True
      prefixlength:
        description: The prefix length of the range to search for
        type: int
        required: False
        default: 28
      title:
        description: The subtext to search for in the range's title
        type: str
        required: False
        default: "free"
"""

EXAMPLES = r"""
- name: get the first matching range with default prefixlength and title substring
  debug:
    msg: "This is the next matching range: {{ lookup('freerange', mm_provider, network) }}"
  vars:
    mm_provider:
      mm_url: http://micetro.example.net
      mm_user: apiuser
      mm_password: apipasswd
    network: examplenet

- name: get the first matching range from multiple network zones with provided prefixlength and title substring
  debug:
    msg: "This is the next matching range: {{ query('freerange', mm_provider, network, prefixlength=28, title="free") }}"
  vars:
    mm_url: http://micetro.example.net
    mm_user: apiuser
    mm_passwd: apipasswd
    network:
      - examplenet
      - examplecom
"""

RETURN = r"""
_list:
  description: A list containing the matching network ranges
  fields:
    0: network CIDRs
"""


class LookupModule(LookupBase):
    """Extension to the base looup."""

    def run(self, terms, variables=None, **kwargs):
        """Variabele terms contains a list with supplied parameters.

        - mm_provider -> Definition of the Micetro API mm_provider
        - Network  -> The zone from which the matching range(s) are found
                      Either: CIDR notation, network notation or network name
                      e.g. 172.16.17.0/24 or 172.16.17.0 or examplenet
                      Either string or list
        """
        # Sufficient parameters
        if len(terms) < 2:
            raise AnsibleError(
                "Insufficient parameters. Need at least: mm_provider and network(s)."
            )

        # Get the parameters
        mm_provider = terms[0]
        if isinstance(terms[1], str):
            networks = [str(terms[1]).strip()]
        else:
            # First make sure all elements are string (Sometimes it's
            # AnsibleUnicode, depending on Ansible and Python version)
            terms[1] = list(map(str, terms[1]))
            networks = list(map(str.strip, terms[1]))

        target_prefix_length = kwargs.get("prefixlength", 28)
        title_text = kwargs.get("title", "free")
        new_title_text = kwargs.get("new_title", "reserved")

        def recurse_ranges(range_obj):
            curr_cidr = range_obj['name']
            print(f"Current range's cidr: {curr_cidr}")
            _, prefix_length = curr_cidr.split("/")
            if int(prefix_length) == int(target_prefix_length) and title_text in range_obj.get("customProperties", {}).get("Title", "").lower():
                # Modify the range's title (e.g. reserve it by changing the title to reserved)
                if new_title_text {
                  range_ref = range_obj['ref']
                  url = f"{range_ref}"
                  databody = {
                    "ref": range_ref
                    "properties": {
                      "Title": new_title_text
                    }
                    "saveComment": "Ansible API"
                  }
                  update_title_res = doapi(url, "PUT", mm_provider, databody)
                  print(f"Update title api call result: {update_title_res}")
                }
                return [curr_cidr]
            elif int(prefix_length) < 28 and range_obj.get("childRanges"):
                # Recurse into child ranges
                for child in range_obj['childRanges']:
                    child_ref = child['ref']
                    url = f"{child_ref}"
                    child_range_result = doapi(url, http_method, mm_provider, {})
                    child_range = child_range_result["message"]["result"]["range"]
                    recurse_result = recurse_ranges(child_range)
                    if recurse_result:
                        return recurse_result
            return []

        # Loop over all networks to find a /28 range
        for network in networks:
            # Get the requested network ranges
            http_method = "GET"
            url = "Ranges"
            databody = {"filter": network}
            network_result = doapi(url, http_method, mm_provider, databody)

            # Check if any ranges were found
            if not network_result.get("message").get("result", {}).get("ranges", []):
                continue

            # Iterate through ranges to find a /28 network
            net_ranges = network_result["message"]["result"]["ranges"]
            for net_range in net_ranges:
                recurse_result = recurse_ranges(net_range)
                if recurse_result:
                    return recurse_result

        # If no /28 network found, raise an error
        print("No /28 network found in the provided ranges.")
        return []







        