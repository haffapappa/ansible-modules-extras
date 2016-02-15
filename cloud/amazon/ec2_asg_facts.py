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
---
module: ec2_asg_facts
short_description: Find auto scaling groups by name and/or tags
description:
  - Searches for and returns list of matching auto scaling groups with comprehensive details
  - Can search by matching name and/or tag(s)
  - If no criteria are specified, will return a list of all auto scaling groups in the specified region
version_added: "2.1"
author: "Allen Sanabria (@linuxdynasty), Tom Bamford (@tombamford)"
options:
  name:
    description:
      - The prefix or name of the auto scaling group(s) you are searching for.
    required: false
  tags:
    description:
      - "A dictionary/hash of tags in the format { tag1_name: 'tag1_value', tag2_name: 'tag2_value' } to match against the auto scaling group(s) you are searching for."
    required: false
  no_result_action:
    description:
      - If no results are returned, you can return either success (with empty results) or failure.
    required: false
    default: success
    choices: [ 'success', 'fail' ]
  limit_results:
    description:
      - Fail if the number of results surpass this limit.
    required: false
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Find all groups
- local_acton:
    module: ec2_asg_facts
  register: asgs

# Find a group with matching name/prefix
- ec2_asg_facts:
    name: public-webserver-asg
  register: asgs

# Find a group with matching tags
- ec2_asg_facts:
    tags:
      project: webapp
      env: production
  register: asgs

# Find a group with matching name/prefix and tags
- ec2_asg_facts:
    name: myproject
    tags:
      env: production
  register: asgs

# Fail if no groups are found
- ec2_asg_facts:
    name: public-webserver-asg
    no_result_action: fail
  register: asgs

# Fail if more than the limit of 3 groups is found.
- ec2_asg_facts:
    name: public-webserver-asg
    no_result_action: fail
    limit_results: 1
  register: asgs
'''

RETURN = '''
---
auto_scaling_group_arn:
    description: The Amazon Resource Name of the ASG
    returned: success
    type: string
    sample: "arn:aws:autoscaling:us-west-2:722373842436:autoScalingGroup:10787c52-0bcb-427d-82ba-c8e4b008ed2e:autoScalingGroupName/public-webapp-production-1"
auto_scaling_group_name:
    description: Name of autoscaling group
    returned: success
    type: str
    sample: "public-webapp-production-1"
availability_zones:
    description: List of Availability Zones that are enabled for this ASG.
    returned: success
    type: list
    sample: ["us-west-2a", "us-west-2b", "us-west-2a"]
created_time:
    description: The date and time this ASG was created, in ISO 8601 format.
    returned: success
    type: string
    sample: "2015-11-25T00:05:36.309Z"
default_cooldown:
    description: The default cooldown time in seconds.
    returned: success
    type: int
    sample: 300
desired_capacity:
    description: The number of EC2 instances that should be running in this group.
    returned: success
    type: int
    sample: 3
health_check_period:
    description: Length of time in seconds after a new EC2 instance comes into service that Auto Scaling starts checking its health.
    returned: success
    type: int
    sample: 30
health_check_type:
    description: The service you want the health status from, one of "EC2" or "ELB".
    returned: success
    type: str
    sample: "ELB"
instances:
    description: List of EC2 instances and their status as it relates to the ASG.
    returned: success
    type: list
    sample: [
        {
            "availability_zone": "us-west-2a",
            "health_status": "Healthy",
            "instance_id": "i-es22ad25",
            "launch_configuration_name": "public-webapp-production-1",
            "lifecycle_state": "InService",
            "protected_from_scale_in": "false"
        }
    ]
launch_configuration_name:
    description: Name of launch configuration associated with the ASG.
    returned: success
    type: str
    sample: "public-webapp-production-1"
load_balancer_names:
    description: List of load balancers names attached to the ASG.
    returned: success
    type: list
    sample: ["elb-webapp-prod"]
max_size:
    description: Maximum size of group
    returned: success
    type: int
    sample: 3
min_size:
    description: Minimum size of group
    returned: success
    type: int
    sample: 1
new_instances_protected_from_scale_in:
    description: Whether or not new instances a protected from automatic scaling in.
    returned: success
    type: boolean
    sample: "false"
placement_group:
    description: Placement group into which instances are launched, if any.
    returned: success
    type: str
    sample: None
status:
    description: The current state of the group when DeleteAutoScalingGroup is in progress.
    returned: success
    type: str
    sample: None
tags:
    description: List of tags for the ASG, and whether or not each tag propagates to instances at launch.
    returned: success
    type: list
    sample: [
        {
            "key": "Name",
            "value": "public-webapp-production-1",
            "resource_id": "public-webapp-production-1",
            "resource_type": "auto-scaling-group",
            "propagate_at_launch": "true"
        },
        {
            "key": "env",
            "value": "production",
            "resource_id": "public-webapp-production-1",
            "resource_type": "auto-scaling-group",
            "propagate_at_launch": "true"
        }
    ]
termination_policies:
    description: A list of termination policies for the group.
    returned: success
    type: str
    sample: ["Default"]
'''

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

def match_asg_tags(tags_to_match, asg):
    for key, value in tags_to_match.iteritems():
        for tag in asg['Tags']:
            if key == tag['Key'] and value == tag['Value']:
                break
        else: return False
    return True

def find_asgs(conn, name=None, tags=None):
    """
    Args:
        conn (boto3.AutoScaling.Client): Valid Boto3 ASG client.
        name (str): Optional name of the ASG you are looking for.
        tags (dict): Optional dictionary of tags and values to search for.

    Basic Usage:
        >>> name = 'public-webapp-production'
        >>> tags = { 'env': 'production' }
        >>> conn = boto3.client('autoscaling', region_name='us-west-2')
        >>> results = find_asgs(name, conn)

    Returns:
        List
        [
            {
                "auto_scaling_group_arn": "arn:aws:autoscaling:us-west-2:275977225706:autoScalingGroup:58abc686-9783-4528-b338-3ad6f1cbbbaf:autoScalingGroupName/public-webapp-production",
                "auto_scaling_group_name": "public-webapp-production",
                "availability_zones": ["us-west-2c", "us-west-2b", "us-west-2a"],
                "created_time": "2016-02-02T23:28:42.481000+00:00",
                "default_cooldown": 300,
                "desired_capacity": 2,
                "enabled_metrics": [],
                "health_check_grace_period": 300,
                "health_check_type": "ELB",
                "instances":
                [
                    {
                        "availability_zone": "us-west-2c",
                        "health_status": "Healthy",
                        "instance_id": "i-047a12cb",
                        "launch_configuration_name": "public-webapp-production-1",
                        "lifecycle_state": "InService",
                        "protected_from_scale_in": false
                    },
                    {
                        "availability_zone": "us-west-2a",
                        "health_status": "Healthy",
                        "instance_id": "i-7a29df2c",
                        "launch_configuration_name": "public-webapp-production-1",
                        "lifecycle_state": "InService",
                        "protected_from_scale_in": false
                    }
                ],
                "launch_configuration_name": "public-webapp-production-1",
                "load_balancer_names": ["public-webapp-production-lb"],
                "max_size": 4,
                "min_size": 2,
                "new_instances_protected_from_scale_in": false,
                "placement_group": None,
                "status": None,
                "suspended_processes": [],
                "tags":
                [
                    {
                        "key": "Name",
                        "propagate_at_launch": true,
                        "resource_id": "public-webapp-production",
                        "resource_type": "auto-scaling-group",
                        "value": "public-webapp-production"
                    },
                    {
                        "key": "env",
                        "propagate_at_launch": true,
                        "resource_id": "public-webapp-production",
                        "resource_type": "auto-scaling-group",
                        "value": "production"
                    }
                ],
                "termination_policies":
                [
                    "Default"
                ],
                "vpc_zone_identifier":
                [
                    "subnet-a1b1c1d1",
                    "subnet-a2b2c2d2",
                    "subnet-a3b3c3d3"
                ]
            }
        ]
    """
    asgs = conn.describe_auto_scaling_groups()['AutoScalingGroups']
    matched_asgs = []
    for asg in asgs:
        if name:
            name_prog = re.compile(r'^' + name)
            matched_name = name_prog.search(asg['AutoScalingGroupName'])
        else: matched_name = True

        if tags: matched_tags = match_asg_tags(tags, asg)
        else: matched_tags = True

        if matched_name and matched_tags:
            asg_details = dict(created_time=asg['CreatedTime'].isoformat())
            camel_prog = re.compile('(?!^)([A-Z]+)')

            for key in ['AutoScalingGroupARN', 'AutoScalingGroupName', 'AvailabilityZones',
                        'DefaultCooldown', 'DesiredCapacity', 'HealthCheckGracePeriod',
                        'HealthCheckType', 'LaunchConfigurationName', 'LoadBalancerNames',
                        'MaxSize', 'MinSize', 'NewInstancesProtectedFromScaleIn',
                        'PlacementGroup' 'Status', 'TerminationPolicies']:
                new_key = camel_prog.sub(r'_\1', key).lower()
                if key in asg:
                    asg_details[new_key] = asg[key]
                else:
                    asg_details[new_key] = None

            for key in ['EnabledMetrics', 'Instances', 'SuspendedProcesses', 'Tags']:
                if key in asg:
                    new_key = camel_prog.sub(r'_\1', key).lower()
                    asg_details[new_key] = []
                    for item in asg[key]:
                        asg_details[new_key].append(dict((camel_prog.sub(r'_\1', k).lower(), v) for k, v in item.iteritems()))

            if 'VPCZoneIdentifier' in asg:
                asg_details['vpc_zone_identifier'] = asg['VPCZoneIdentifier'].split(',')
            else:
                asg_details['vpc_zone_identifier'] = None

            matched_asgs.append(asg_details)
    return matched_asgs

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            name=dict(type='str'),
            tags=dict(type='dict'),
            limit_results=dict(required=False, type='int', default=0),
            no_result_action = dict(
                required=False, type='str', default='success',
                choices = ['success', 'fail']
            ),
        )
    )
    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    asg_name = module.params.get('name')
    asg_tags = module.params.get('tags')
    no_result_action = module.params.get('no_result_action')
    limit_results = module.params.get('limit_results')

    try:
        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        autoscaling = boto3_conn(module, conn_type='client', resource='autoscaling', region=region, endpoint=ec2_url, **aws_connect_kwargs)
    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg="Can't authorize connection - " + str(e))

    results = find_asgs(autoscaling, name=asg_name, tags=asg_tags)
    if limit_results > 0 and len(results) > limit_results:
        asg_names = [a['auto_scaling_group_name'] for a in results]
        msg = (
            "More than {0} ASG with name={1} found.".
            format(str(limit_results), name)
        )
        module.fail_json(msg=msg, asg_names=asg_names)

    elif no_result_action == 'fail' and not results:
        module.fail_json(msg='No results found')

    elif not results and no_result_action == 'success':
        output = {
            "changed" : False,
            "rc" : 0,
            "results": results
        }

    elif results:
        output = {
            "changed" : True,
            "rc" : 0,
            "results": results
        }

    module.exit_json(**output)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
