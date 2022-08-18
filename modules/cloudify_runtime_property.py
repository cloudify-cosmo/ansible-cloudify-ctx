# Copyright (c) 2016-2022 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'supported_by': 'community',
    'status': ['preview']
}

DOCUMENTATION = '''
---
module: cloudify_ctx
author: Cloudify (@cloudify-cosmo)
short_description: Interact with Cloudify CTX analog from within Ansible Playbooks.
description:
    - Store ansible facts and other output to runtime properties.
version_added: "2.9"
options:
  path:
    description:
      - The name of the runtime property or the path to the runtime property. For example, the runtime property can be "foo". For the path could be "foo.bar.-1.". This would assign a value "new" to: {'foo': {'bar': ["new"]}}.
    required: true
    default: ansible_facts
    aliases:
      - name
  value:
    description:
      - The playbook syntax to access the value to store in the runtime property.
    required: true
    default: null
    alias: []
  node_instance_id:
    description:
      - The ID of the node instance that you want to modify.
    required: false
    default: null
  client_kwargs:
    description: A dict of keyword args when initializing the Cloudify Rest Client. If this is not provided, the module attempts to use the current environment. See https://github.com/cloudify-cosmo/cloudify-common/blob/6.3.0-build/cloudify/manager.py#L146.
    required: false.
    aliases: [rest_client_kwargs, credentials].
requirements:
    - python >= 2.6
    - cloudify-common >= 6.3.0
'''

EXAMPLES = '''
# Create an AWS Elastic IP and Assign it to a runtime property.
    - name: Create elastic ip
      ec2_eip:
        device_id: "{{ eni_id }}"
        in_vpc: yes
        public_ipv4_pool: yes
        tag_name: Name
        tag_value: "{{ eip_name }}"
        release_on_disassociation: yes
      register: eip

    - name: Store EIP
      cloudify_runtime_property:
        path: ip_address
        value: "{{ eip.public_ip }}"

# Create a Kubernetes Resource and Get Status
    - name: Create a Pod object by reading the definition from a file
      k8s:
        state: present
        src: /testing/pod.yml
    
    - name: Get an existing Service object
      k8s:
        apiVersion: v1
        kind: Pod
        metadata:
          name: nginx
        spec:
          containers:
          - name: nginx
            image: nginx:1.14.2
            ports:
            - containerPort: 80
      register: nginx_app

    - name: Store Deployment status.
      cloudify_runtime_property:
        name: kubernetes_resources.app
        value: "{{ nginx_app.status }}"

    - name: Create a Service object by reading the definition from a file
      k8s:
        state: present
        src: /testing/service.yml
    
    - name: Get an existing Service object
      k8s:
        api_version: v1
        kind: Service
        name: web
        namespace: testing
      register: web_service

    - name: Store Deployment status.
      cloudify_runtime_property:
        path: kubernetes_resources.service
        value: "{{ web_service.result.status }}"

'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'ok'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'ok'
'''

import os
import sys
import json
from distutils.version import StrictVersion


def get_site_packages():
    def _get_formatted_version(version):
        try:
            version = version.replace('python', '')
            return StrictVersion(version)
        except ValueError:
            return None

    path_base = '/opt/mgmtworker/env/lib'
    package_dirs = next(os.walk(path_base))[1]
    versions = package_dirs
    newest = max(versions, key=_get_formatted_version)
    path_base += '/{0}/site-packages'.format(newest)
    return path_base

try:
    from cloudify.cluster import CloudifyClusterClient
    from cloudify_rest_client.exceptions import CloudifyClientError
except ImportError:
    site_packages = get_site_packages()
    sys.path.append(site_packages)
    try:
        from cloudify.cluster import CloudifyClusterClient
        from cloudify_rest_client.exceptions import CloudifyClientError
    except ImportError as e:
        raise RuntimeError(
            'Unable to locate package cloudify in {}.'
            'Unable to locate package cloudify in {}.'
            ' Original exception: {}'.format(
                os.environ.get('PYTHONPATH'),
                sys.path,
                str(e))
        )

from ansible.module_utils.basic import AnsibleModule

TENANT = 'default_tenant'
REQUIRED_NON_SSL = ['username', 'password']
REQUIRED_ENV = ['REST_PORT', 'REST_HOST', 'LOCAL_REST_CERT_FILE']


def get_cloudify_client(client_kwargs=None):
    client_kwargs = client_kwargs or {}
    if not set(REQUIRED_ENV) <= set(os.environ) and not client_kwargs:
        raise RuntimeError(
            'Unable to execute module without required '
            'environment variables: {}'.format(REQUIRED_ENV))

    rest_port = int(os.environ['REST_PORT'])
    if rest_port != 80:
        ssl_cert_path = os.environ['LOCAL_REST_CERT_FILE']
        protocol = 'https'
    else:
        if not set(REQUIRED_NON_SSL) <= set(client_kwargs.keys()):
            raise RuntimeError(
                'Unable to execute module without required '
                'client kwargs: {}'.format(REQUIRED_NON_SSL)
            )
        ssl_cert_path = None
        protocol = 'http'

    kwargs = {
        'host': os.environ['REST_HOST'],
        'port': rest_port,
        'cert': ssl_cert_path,
        'protocol': protocol,
        'tenant': TENANT,
    }
    kwargs.update(client_kwargs)
    try:
        client = CloudifyClusterClient(**kwargs)
        client.manager.get_status()
        return client
    except CloudifyClientError:
        kwargs = load_local_client_config()
        kwargs.update(client_kwargs)
        client = CloudifyClusterClient(**kwargs)
        client.manager.get_status()
        return client


def load_local_client_config():
    f = open('{}/.cloudify/profiles/manager-local/context.json'.format(
        os.path.expanduser('~')))
    j = json.load(f)
    f.close()
    return {
        'host': j.get('manager_ip'),
        'port': j.get('rest_port'),
        'protocol': j.get('rest_protocol'),
        'tenant': j.get('manager_tenant'),
        'username': j.get('manager_username'),
        'password': j.get('manager_password'),
    }


def assign_dot_json(dj, paths, value):
    curr = dj
    keys = paths.split('.')
    final_key = keys.pop()
    for key in keys:
        result = getattr(curr, key, None)
        if result is None:
            setattr(curr, key, DotJson())
        curr = getattr(curr, key)
    setattr(curr, final_key, value)


class DotJson(dict):

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    @property
    def __dict__(self):
        new_dict = {}
        for var in vars(self):
            new_dict[var] = getattr(var)

    def __init__(self, value=None):

        def recurse(d):
            if isinstance(d, dict):
                new_d = {}
                for key, value in d.items():
                    new_d[key] = recurse(value)
                return DotJson(new_d)
            elif isinstance(d, list):
                new_l = []
                for i in d:
                    new_l.append(recurse(i))
            else:
                return d

        if isinstance(value, dict):
            for key, value in value.items():
                setattr(self, key, recurse(value))


def update_runtime_property(path, value, node_instance_id, rest_client):
    instance = rest_client.node_instances.get(node_instance_id)
    props = DotJson(instance.runtime_properties)
    assign_dot_json(props, path, value)
    return rest_client.node_instances.update(
        node_instance_id=node_instance_id,
        state=instance.state,
        runtime_properties=props,
        version=int(instance.version) + 1)


def setup_module():
    module_args = dict(
        path=dict(type='str', required=True),
        value=dict(required=True),
        node_instance_id=dict(type='str', required=False),
        client_kwargs=dict(type='dict', required=False),
        name=dict(type='str', required=False),
    )
    return AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )


def perform_cloudify_runtime(result,
                             path,
                             value,
                             node_instance_id,
                             client_kwargs):

    try:
        cloudify_client = get_cloudify_client(client_kwargs)
    except (RuntimeError, CloudifyClientError) as e:
        result['changed'] = False
        result['messaage'] = str(e)
        raise e

    try:
        response = update_runtime_property(
            path,
            value,
            node_instance_id,
            cloudify_client
        )
    except Exception as e:
        if hasattr(e, 'message'):
            result['message'] = e.message
        else:
            result['message'] = str(e)
    else:
        result['changed'] = True
        result['message'] = response
    return result


def run_module():
    module = setup_module()

    result = dict(
        changed=False,
        original_message='',
        message=''
    )
    path = module.params.get('path')
    value = module.params.get('value')
    node_instance_id = module.params.get(
        'node_instance_id')

    if not node_instance_id:
        node_instance_id = os.environ.get('CTX_NODE_INSTANCE_ID')

    result = perform_cloudify_runtime(
        result,
        path,
        value,
        node_instance_id,
        module.params.get('client_kwargs', {})
    )

    module.exit_json(**result)


if __name__ == '__main__':
    run_module()
