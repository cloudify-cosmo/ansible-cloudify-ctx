# ansible-cloudify-ctx

An ansible module that enables users to perform some ctx-like tasks with Cloudify in ansible playbooks.

## Requirements

  * Cloudify Ansible Plugin 2.13.16, or higher.
  * Cloudify Manager 6.4, or higher.
  * A Cloudify Manager that supports SSL, or your Cloudify manager rest credentials.

## Manager preparation

You must install the ansible module in one of the appropriate paths for ansible modules, for example `/etc/cloudify/.ansible/plugins/modules.`.

You must collect your Cloudify manager credentials.

The module will try to use environment variables to connect to Cloudify Manager, 
however, if your manager is not configured for SSL or if your security does not permit, 
you must provide credentials directly in the playbook.

The module will try to load the Cloudify Rest Client from `/opt/mgmtworker/env/lib/python3.6/site-packages/`.
If this path does not contain `cloudify_rest_client` or if it doesn't exist at all, 
or if it's not valid anymore, then the module will not work.

## Using the module:

This module will only work in localhost mode on Cloudify Manager host.

Simple Example:

```yaml
- hosts: localhost
  tasks:
    - name: simple runtime property
      cloudify_runtime_property:
        path: hello
        value: world
```

This will create a property `hello` with the value `world`.

Nested Dict Example:

```yaml
- hosts: localhost
  tasks:
    - name: complex runtime property part I
      cloudify_runtime_property:
        path: foo.bar
        value: baz

    - name: complex runtime property part II
      cloudify_runtime_property:
        path: foo.qux
        value: quux

```

This will create a dict `foo` wth the value: `{'bar': 'baz', 'qux': 'quux'}`.

Providing credentials:

```yaml
- hosts: localhost
  tasks:
    - name: simple runtime property
      cloudify_runtime_property:
        path: hello
        value: world
        client_kwargs:
          username: cooluser
          password: supersecret123
          tenant: nicetenant
          protocol: http
```
