#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2020, Men&Mice
# GNU General Public License v3.0
# see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt
#
# python 3 headers, required if submitting to Ansible
"""Ansible lookup plugin.

Lookup plugin for finding the next free IP address in
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
    lookup: freeip
    author: Ton Kersten <t.kersten@atcomputing.nl> for Men&Mice
    version_added: "2.7"
    short_description: Find free IP address(es) in a given network range in the Micetro
    description:
      - This lookup returns free IP address(es) in a range or ranges
        specified by the network names C(e.g. examplenet). This can be
        a string or a list
      - If multiple IP addresses are returned, the results will be returned as
        a comma-separated list.
        In such cases you may want to pass option C(wantlist=True) to the plugin,
        which will result in the record values being returned as a list
        over which you can iterate later on (or use C(query) instead)
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
          - network zone(s) from which the first free IP address is to be found.
          - This is either a single network or a list of networks
        type: list
        required: True
      multi:
        description: Get a list of x number of free IP addresses from the
          requested zones
        type: int
        required: False
        default: False
      claim:
        description: Claim the IP address(es) for the specified amount of time in seconds
        type: int
        required: False
      ping:
        description: ping the address found before returning
        type: bool
        required: False
        default: False
      excludedhcp:
        description: exclude DHCP reserved ranges from result
        type: bool
        required: False
        default: False
      startaddress:
        description:
          - Start address when looking for the next free address
          - When the start address is not in de zone it will be ignored
        type: str
        required: False
        default: None
      filter:
        description:
          - Micetro filter statement
          - Filter validation is done by the Micetro, not in the plugin
          - More filter info on https://docs.menandmice.com/display/MM930/Quickfilter
        type: str
        required: False
        default: None
"""

EXAMPLES = r"""
- name: get the first free IP address in a zone
  debug:
    msg: "This is the next free IP: {{ lookup('menandmice.ansible_micetro.freeip', mm_provider, network) }}"
  vars:
    mm_provider:
      mm_url: http://micetro.example.net
      mm_user: apiuser
      mm_password: apipasswd
    network: examplenet

- name: get the first free IP addresses in multiple zones
  debug:
    msg: "This is the next free IP: {{ query('menandmice.ansible_micetro.freeip', mm_provider, network, multi=5, claim=60) }}"
  vars:
    mm_url: http://micetro.example.net
    mm_user: apiuser
    mm_passwd: apipasswd
    network:
      - examplenet
      - examplecom

  - name: get the first free IP address in a zone and ping
    debug:
      msg: "This is the next free IP: {{ query('menandmice.ansible_micetro.freeip', mm_provider, network, ping=True) }}"
    vars:
      mm_url: http://micetro.example.net
      mm_user: apiuser
      mm_passwd: apipasswd
      network: examplenet
"""

RETURN = r"""
_list:
  description: A list containing the free IP address(es) in the network range
  fields:
    0: IP address(es)
"""


class LookupModule(LookupBase):
    """Extension to the base looup."""

    def run(self, terms, variables=None, **kwargs):
        """Variabele terms contains a list with supplied parameters.

        - mm_provider -> Definition of the Micetro API mm_provider
        - Network  -> The zone from which the free IP address(es) are found
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

        def recurse_ranges(range_obj):
            curr_cidr = range_obj['name']
            print(f"Current range's cidr: {curr_cidr}")
            _, prefix_length = curr_cidr.split("/")
            if int(prefix_length) == int(target_prefix_length) and title_text in range_obj.get("customProperties", {}).get("Title", "").lower():
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







        