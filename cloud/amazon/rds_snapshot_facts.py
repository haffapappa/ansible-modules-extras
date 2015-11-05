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
module: rds_snapshot_facts
short_description: searches for rds snapshots to obtain the id
description:
    - searches for rds snapshots to obtain the id
options:
  snapshot_id:
    description:
      - id of the snapshot to search for
    required: false
  instance_id:
    description:
      - id of a DB instance
    required: false
  max_records:
    description:
      - max records returned
    required: false

author: "Brock Haywood (@brockhaywood)"
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Basic Snapshot Search
- local_action:
    module: rds_snapshot_facts
    snapshot_id: my-local-snapshot
# Find all
- local_action:
    module: rds_snapshot_facts
'''

try:
    import boto.rds
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def find_snapshot_facts(module, conn, snapshot_id=None, instance_id=None, max_records=None):

    try:
        snapshots = conn.get_all_dbsnapshots(snapshot_id=snapshot_id, instance_id=instance_id, max_records=max_records)
    except boto.exception.BotoServerError, e:
        module.fail_json(msg="%s: %s" % (e.error_code, e.error_message))

    results = []

    for snapshot in snapshots:
        results.append({
            'engine_version': snapshot.engine_version,
            'allocated_storage': snapshot.allocated_storage,
            'availability_zone': snapshot.availability_zone,
            'id': snapshot.id,
            'instance_create_time': snapshot.instance_create_time,
            'instance_id': snapshot.instance_id,
            'master_username': snapshot.master_username,
            'port': snapshot.port,
            'status': snapshot.status,
            'option_group_name': snapshot.option_group_name,
            'snapshot_create_time': snapshot.snapshot_create_time,
            'snapshot_type': snapshot.snapshot_type,
            'source_region': snapshot.source_region,
            'vpc_id': snapshot.vpc_id
        })

    module.exit_json(results=results)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            snapshot_id=dict(),
            instance_id=dict(),
            max_records=dict(),
        )
    )
    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    snapshot_id = module.params.get('snapshot_id')
    instance_id = module.params.get('instance_id')
    max_records = module.params.get('max_records')

    # Retrieve any AWS settings from the environment.
    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module)

    if not region:
        module.fail_json(msg=str("Either region or AWS_REGION or EC2_REGION "
                                 "environment variable or boto config "
                                 "aws_region or ec2_region must be set."))

    try:
        conn = connect_to_aws(boto.rds, region, **aws_connect_kwargs)

        find_snapshot_facts(
            module=module,
            conn=conn,
            snapshot_id=snapshot_id,
            instance_id=instance_id,
            max_records=max_records
        )

    except boto.exception.BotoServerError, e:
        module.fail_json(msg=e.error_message)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
