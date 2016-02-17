#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
module: route53_zone
short_description: add or delete Route53 zones
description:
    - Creates and deletes Route53 private and public zones
version_added: "2.0"
options:
    zone:
        description:
            - "The DNS zone record (eg: foo.com.)"
        required: true
    state:
        description:
            - whether or not the zone should exist or not
        required: false
        default: true
        choices: [ "present", "absent" ]
    vpc_id:
        description:
            - The VPC ID the zone should be a part of (if this is going to be a private zone)
        required: false
        default: null
    vpc_region:
        description:
            - The VPC Region the zone should be a part of (if this is going to be a private zone)
        required: false
        default: null
    comment:
        description:
            - Comment associated with the zone
        required: false
        default: ''
    delegation_set:
        description:
            - Optional ID of a delegation set to use when state=present instead of creating a new delegation set.
        required: false
        default: null
        version_added: 2.1
extends_documentation_fragment:
    - aws
    - ec2
author: "Christopher Troup (@minichate), Tom Bamford (@tombamford)"
'''

EXAMPLES = '''
# create a public zone
- route53_zone: zone=example.com state=present comment="this is an example"

# delete a public zone
- route53_zone: zone=example.com state=absent

- name: private zone for devel
  route53_zome: zone=devel.example.com state=present vpc_id={{myvpc_id}} comment='developer domain'

# more complex example
- name: register output after creating zone in parameterized region
  route53_zone:
    vpc_id: "{{ vpc.vpc_id }}"
    vpc_region: "{{ ec2_region }}"
    zone: "{{ vpc_dns_zone }}"
    state: present
    register: zone_out

- debug: var=zone_out

# create a public zone with specified delegation set
- route53_zone:
    zone: example.com
    comment: 'an example'
    delegation_set: N4FE26DK7WIZ83
    state: present

'''

RETURN = '''
---
delegation_set:
    description: The delegation set ID, if the zone is linked to one.
    returned: success
    type: string
    sample: "N4FE26DK7WIZ83"
location:
    description: Hyperlink to the created Route53 object.
    returned: changed
    type: str
    sample: "public-webapp-production-1"
name:
    description: The zone name (with trailing dot).
    returned: success
    type: str
    sample: "example.com."
name_servers:
    description: List of authoritative name servers for the zone.
    returned: success
    type: list
    sample: ["ns-495.awsdns-61.com", "ns-705.awsdns-24.net", "ns-1128.awsdns-13.org", "ns-1741.awsdns-25.co.uk"]
private_zone:
    description: Whether the zone is private.
    returned: success
    type: bool
    sample: false
resource_record_set_count:
    description: The number of resource record sets in the hosted zone.
    returned: success
    type: int
    sample: 5
zone_id:
    description: Unique identifier for the hosted zone.
    returned: success
    type: str
    sample: Z4C5RXH24EJ2LQ
'''


import datetime, random

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            zone=dict(type='str', required=True),
            state=dict(type='str', default='present', choices=['present', 'absent']),
            vpc_id=dict(type='str', default=None),
            vpc_region=dict(type='str', default=None),
            comment=dict(type='str', default=''),
            delegation_set=dict(type='str', default=None))),
    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    zone_in = module.params.get('zone').lower()
    state = module.params.get('state').lower()
    vpc_id = module.params.get('vpc_id')
    vpc_region = module.params.get('vpc_region')
    comment = module.params.get('comment')
    delegation_set = module.params.get('delegation_set')

    if zone_in[-1:] != '.':
        zone_in += "."

    private_zone = vpc_id is not None and vpc_region is not None
    caller_reference = 'ansible-route53_zone-%s-%s' % (datetime.datetime.utcnow().isoformat(), random.randint(100000, 999999))

    zone_key = zone_in + ':' + (vpc_id or '')

    # connect to the route53 endpoint
    try:
        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        route53 = boto3_conn(module, conn_type='client', resource='route53', region=region, endpoint=ec2_url, **aws_connect_kwargs)
    except botocore.exceptions.ClientError, e:
        module.fail_json(msg=e.response['Error']['Message'])

    results = route53.list_hosted_zones()

    for r53zone in results['HostedZones']:
        if r53zone['Name'] == zone_in:
            zone_id = r53zone['Id'].replace('/hostedzone/', '')
            zone_details = route53.get_hosted_zone(Id=zone_id)
            if vpc_id and 'VPCs' in zone_details and vpc_id in [v['VPCId'] for v in zone_details['VPCs']]:
                break
            elif not vpc_id and 'VPCs' not in zone_details:
                break
    else:
        zone_id = None

    record = dict(CallerReference=caller_reference)

    if comment:
        record['HostedZoneConfig'] = dict(Comment=comment)

    if private_zone:
        record['VPC'] = dict(VPCId=vpc_id, VPCRegion=vpc_region)

    if delegation_set:
        if private_zone:
            module.fail_json(msg='Cannot specify delegation_set for private zone')
        delegation_set = "/delegationset/{0}".format(delegation_set)
        try:
            deleg_set_result = route53.get_reusable_delegation_set(Id=delegation_set)
        except botocore.exceptions.ClientError, e:
            if e.response['Error']['Code'] == 'NoSuchDelegationSet':
                module.fail_json(msg='The specified delegation set was not found')
            else:
                module.fail_json(msg=e.response['Error']['Message'])
        record['DelegationSetId'] = delegation_set

    if state == 'present' and zone_id:
        details = route53.get_hosted_zone(Id=zone_id)
        result = dict(
            zone_id=details['HostedZone']['Id'].replace('/hostedzone/', ''),
            name=details['HostedZone']['Name'],
            private_zone=details['HostedZone']['Config']['PrivateZone'],
            resource_record_set_count=details['HostedZone']['ResourceRecordSetCount'],
        )

        if 'Comment' in details['HostedZone']['Config']:
            result['comment'] = details['HostedZone']['Config']['Comment']

        if 'DelegationSet' in details:
            result['name_servers'] = details['DelegationSet']['NameServers'],

        if delegation_set:
            if 'Id' not in details['DelegationSet'] or details['DelegationSet']['Id'] != delegation_set:
                module.fail_json(msg='Cannot change the delegation set for an existing zone')
            else:
                result['delegation_set'] = details['DelegationSet']['Id'].replace('/delegationset/', '')

        if 'VPCs' in details:
            result['vpcs'] = [dict(id=v['VPCId'], region=v['VPCRegion']) for v in details['VPCs']]

        module.exit_json(changed=False, result=result)

    elif state == 'present':
        try:
            create_result = route53.create_hosted_zone(Name=zone_in, **record)
        except botocore.exceptions.ClientError, e:
            module.fail_json(msg=e.response['Error']['Message'])

        result = dict(
            zone_id=create_result['HostedZone']['Id'].replace('/hostedzone/', ''),
            name=create_result['HostedZone']['Name'],
            private_zone=create_result['HostedZone']['Config']['PrivateZone'],
            resource_record_set_count=create_result['HostedZone']['ResourceRecordSetCount'],
            location=create_result['Location'],
        )

        if 'Comment' in create_result['HostedZone']['Config']:
            result['comment'] = create_result['HostedZone']['Config']['Comment']

        if 'DelegationSet' in create_result:
            result['name_servers'] = create_result['DelegationSet']['NameServers'],
            if 'Id' in create_result['DelegationSet']:
                result['delegation_set'] = create_result['DelegationSet']['Id'].replace('/delegationset/', '')

        if 'VPCs' in create_result:
            result['vpcs'] = [dict(id=v['VPCId'], region=v['VPCRegion']) for v in create_result['VPCs']]

        module.exit_json(changed=True, result=result)

    elif state == 'absent' and zone_id:
        route53.delete_hosted_zone(Id=zone_id)
        module.exit_json(changed=True)

    elif state == 'absent':
        module.exit_json(changed=False)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
