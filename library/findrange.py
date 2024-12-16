#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2020, Men&Mice
# GNU General Public License v3.0
# see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt
#
# python 3 headers, required if submitting to Ansible
"""Ansible module.

Module for finding an acceptable range in
a network zone in the Micetro.
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.menandmice.ansible_micetro.plugins.module_utils.micetro import (
    doapi,
)

DOCUMENTATION = r"""
    module: findrange
    short_description: Find the first acceptable network range
    description:
      - This module looks for a network range with the provided prefixlength 
        and a title that contains the provided title input within the provided input network zone(s)
      - If a range like that is found, the new_title (if provided) will override the range's old title
      - Dry-run or check-mode is possible. In these cases this module only looks for the range,
        but does NOT modify the title (however the result's 'changed' field will be set to True in order to simulate changes)
      - If no range is found, the module fails with an error message
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
        required: True
      title:
        description: The subtext to search for in the range's title
        type: str
        required: False
        default: ""
      new_title:
        description: The text what the range's title should be replaced to
        type: str
        required: False
        default: ""
"""

EXAMPLES = r"""
- name: Add a reservation for a network range
  findrange:
    mm_provider:
      mm_url: http://micetro.example.net
      mm_user: apiuser
      mm_password: apipasswd
    network: 192.168.0.0/24
    prefixlength: 28
    title: free
    new_title: reserved
  delegate_to: localhost
"""

RETURN = r"""
message:
    description: The CIDR of the found range.
    type: str
    returned: always
"""


def run_module():
    # Define available arguments/parameters a user can pass to the module
    module_args = dict(
        mm_provider=dict(
            type="dict",
            required=True,
            options=dict(
                mm_url=dict(type="str", required=True, no_log=False),
                mm_user=dict(type="str", required=True, no_log=False),
                mm_password=dict(type="str", required=True, no_log=True),
            ),
        ),
        network=dict(type="list", required=True),
        prefixlength=dict(type="int", required=True),
        title=dict(type="str", required=False, default=""),
        new_title=dict(type="str", required=False, default="")

    )

    # Seed the result dict in the object
    module_result = {"changed": False, "message": ""}

    # Initialize the module
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Get the parameters
    mm_provider = module.params["mm_provider"]
    try:
        # Ensure all elements are strings and strip whitespace
        networks = [str(net).strip() for net in module.params["network"] if net]
    except Exception as e:
        module.fail_json(msg=f"Error processing networks input: {str(e)}")
    target_prefix_length = module.params["prefixlength"]
    title_text = module.params["title"]
    new_title_text = module.params["new_title"]


    def doapi_with_errcheck(url, method, mm_provider, databody):
        doapi_result = doapi(url, method, mm_provider, databody)
        doapi_warnings = doapi_result.get("warnings", "")
        if doapi_warnings:
            module.fail_json(msg=f"{doapi_warnings}")
        return doapi_result


    def recurse_ranges(range_obj):
        curr_cidr = range_obj["name"]
        print(f"Current range's cidr: {curr_cidr}")
        _, prefix_length = curr_cidr.split("/")
        if int(prefix_length) == int(target_prefix_length) and title_text in range_obj.get("customProperties", {}).get("Title", "").lower():
            # Modify the range's title (e.g. reserve it by changing the title to reserved)
            if new_title_text:
                if not module.check_mode:
                    range_ref = range_obj["ref"]
                    url = f"{range_ref}"
                    http_method = "PUT"
                    databody = {
                      "ref": range_ref,
                      "properties": {
                        "Title": new_title_text
                      },
                      "saveComment": "Ansible API"
                    }
                    update_title_res = doapi_with_errcheck(url, http_method, mm_provider, databody)
                module_result["changed"] = True
            module_result["message"] = curr_cidr
            module.exit_json(**module_result)
        elif int(prefix_length) < 28 and range_obj.get("childRanges"):
            # Recurse into child ranges
            for child in range_obj["childRanges"]:
                child_ref = child["ref"]
                url = f"{child_ref}"
                http_method = "GET"
                child_range_result = doapi_with_errcheck(url, http_method, mm_provider, {})
                child_range = child_range_result["message"]["result"]["range"]
                recurse_ranges(child_range)

    # Loop over all networks to find a desirable network range
    for network in networks:
        # Get the requested network ranges
        http_method = "GET"
        url = "Ranges"
        databody = {"filter": network}
        network_result = doapi_with_errcheck(url, http_method, mm_provider, databody)

        # Check if any ranges were found
        if not network_result.get("message").get("result", {}).get("ranges", []):
            continue

        # Iterate through ranges to find a desirable network range
        net_ranges = network_result["message"]["result"]["ranges"]
        for net_range in net_ranges:
            recurse_ranges(net_range)

    # If no acceptable range found, raise an error
    module.fail_json(msg=f"No acceptable /{target_prefix_length} range found in the provided network(s).")


def main():
    run_module()


if __name__ == "__main__":
    main()
  