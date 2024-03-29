# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

from eventlet import greenthread
import mock
from oslo.config import cfg

from neutron.api.v2 import attributes
from neutron import context
from neutron.extensions import l3
from neutron.manager import NeutronManager
from neutron.openstack.common import uuidutils
from neutron.plugins.nicira import NeutronServicePlugin as nsp
from neutron.plugins.nicira import nvplib
from neutron.tests import base
from neutron.tests.unit.nicira import NVPEXT_PATH
from neutron.tests.unit.nicira import SERVICE_PLUGIN_NAME
from neutron.tests.unit.nicira import test_nicira_plugin
from neutron.tests.unit.nicira import VCNS_NAME
from neutron.tests.unit.nicira.vshield import fake_vcns
from neutron.tests.unit import test_l3_plugin

_uuid = uuidutils.generate_uuid


class ServiceRouterTestExtensionManager(object):

    def get_resources(self):
        # If l3 resources have been loaded and updated by main API
        # router, update the map in the l3 extension so it will load
        # the same attributes as the API router
        l3_attr_map = copy.deepcopy(l3.RESOURCE_ATTRIBUTE_MAP)
        for res in l3.RESOURCE_ATTRIBUTE_MAP.keys():
            attr_info = attributes.RESOURCE_ATTRIBUTE_MAP.get(res)
            if attr_info:
                l3.RESOURCE_ATTRIBUTE_MAP[res] = attr_info
        resources = l3.L3.get_resources()
        # restore the original resources once the controllers are created
        l3.RESOURCE_ATTRIBUTE_MAP = l3_attr_map

        return resources

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class NvpRouterTestCase(test_nicira_plugin.TestNiciraL3NatTestCase):

    def setUp(self, plugin=None, ext_mgr=None, service_plugins=None):
        plugin = plugin or SERVICE_PLUGIN_NAME
        # Disable the proxying in the tests but functionality will
        # be covered separately
        mock_proxy = mock.patch(
            "%s.%s" % (SERVICE_PLUGIN_NAME, '_set_create_lswitch_proxy'))
        mock_proxy.start()
        super(NvpRouterTestCase, self).setUp(plugin=plugin, ext_mgr=ext_mgr,
                                             service_plugins=service_plugins)


class ServiceRouterTest(test_nicira_plugin.NiciraL3NatTest,
                        test_l3_plugin.L3NatTestCaseMixin):

    def vcns_patch(self):
        instance = self.mock_vcns.start()
        self.vcns_instance = instance
        instance.return_value.deploy_edge.side_effect = self.fc2.deploy_edge
        instance.return_value.get_edge_id.side_effect = self.fc2.get_edge_id
        instance.return_value.get_edge_deploy_status.side_effect = (
            self.fc2.get_edge_deploy_status)
        instance.return_value.delete_edge.side_effect = self.fc2.delete_edge
        instance.return_value.update_interface.side_effect = (
            self.fc2.update_interface)
        instance.return_value.get_nat_config.side_effect = (
            self.fc2.get_nat_config)
        instance.return_value.update_nat_config.side_effect = (
            self.fc2.update_nat_config)
        instance.return_value.delete_nat_rule.side_effect = (
            self.fc2.delete_nat_rule)
        instance.return_value.get_edge_status.side_effect = (
            self.fc2.get_edge_status)
        instance.return_value.get_edges.side_effect = self.fc2.get_edges
        instance.return_value.update_routes.side_effect = (
            self.fc2.update_routes)
        instance.return_value.create_lswitch.side_effect = (
            self.fc2.create_lswitch)
        instance.return_value.delete_lswitch.side_effect = (
            self.fc2.delete_lswitch)
        instance.return_value.get_loadbalancer_config.side_effect = (
            self.fc2.get_loadbalancer_config)
        instance.return_value.enable_service_loadbalancer.side_effect = (
            self.fc2.enable_service_loadbalancer)

    def setUp(self, ext_mgr=None, service_plugins=None):
        cfg.CONF.set_override('api_extensions_path', NVPEXT_PATH)
        cfg.CONF.set_override('task_status_check_interval', 100, group="vcns")

        # vcns does not support duplicated router name, ignore router name
        # validation for unit-test cases
        self.fc2 = fake_vcns.FakeVcns(unique_router_name=False)
        self.mock_vcns = mock.patch(VCNS_NAME, autospec=True)
        self.vcns_patch()
        mock_proxy = mock.patch(
            "%s.%s" % (SERVICE_PLUGIN_NAME, '_set_create_lswitch_proxy'))
        mock_proxy.start()

        ext_mgr = ext_mgr or ServiceRouterTestExtensionManager()
        super(ServiceRouterTest, self).setUp(
            plugin=SERVICE_PLUGIN_NAME,
            service_plugins=service_plugins,
            ext_mgr=ext_mgr)

        self.fc2.set_fake_nvpapi(self.fc)
        self.addCleanup(self.fc2.reset_all)
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        plugin = NeutronManager.get_plugin()
        manager = plugin.vcns_driver.task_manager
        for i in range(20):
            if not manager.has_pending_task():
                break
            greenthread.sleep(0.1)
        if manager.has_pending_task():
            manager.show_pending_tasks()
            raise Exception(_("Tasks not completed"))
        manager.stop()
        # Ensure the manager thread has been stopped
        self.assertIsNone(manager._thread)
        super(ServiceRouterTest, self).tearDown()

    def _create_router(self, fmt, tenant_id, name=None,
                       admin_state_up=None, set_context=False,
                       arg_list=None, **kwargs):
        data = {'router': {'tenant_id': tenant_id}}
        if name:
            data['router']['name'] = name
        if admin_state_up:
            data['router']['admin_state_up'] = admin_state_up
        for arg in (('admin_state_up', 'tenant_id') + (arg_list or ())):
            # Arg must be present and not empty
            if arg in kwargs and kwargs[arg]:
                data['router'][arg] = kwargs[arg]
        data['router']['service_router'] = True
        router_req = self.new_create_request('routers', data, fmt)
        if set_context and tenant_id:
            # create a specific auth context for this request
            router_req.environ['neutron.context'] = context.Context(
                '', tenant_id)

        return router_req.get_response(self.ext_api)


class ServiceRouterTestCase(ServiceRouterTest, NvpRouterTestCase):

    def test_router_create(self):
        name = 'router1'
        tenant_id = _uuid()
        expected_value = [('name', name), ('tenant_id', tenant_id),
                          ('admin_state_up', True),
                          ('external_gateway_info', None),
                          ('service_router', True)]
        with self.router(name=name, admin_state_up=True,
                         tenant_id=tenant_id) as router:
            expected_value_1 = expected_value + [('status', 'PENDING_CREATE')]
            for k, v in expected_value_1:
                self.assertEqual(router['router'][k], v)

            # wait ~1 seconds for router status update
            for i in range(2):
                greenthread.sleep(0.5)
                res = self._show('routers', router['router']['id'])
                if res['router']['status'] == 'ACTIVE':
                    break
            expected_value_2 = expected_value + [('status', 'ACTIVE')]
            for k, v in expected_value_2:
                self.assertEqual(res['router'][k], v)

            # check an integration lswitch is created
            lswitch_name = "%s-ls" % name
            for lswitch_id, lswitch in self.fc2._lswitches.iteritems():
                if lswitch['display_name'] == lswitch_name:
                    break
            else:
                self.fail("Integration lswitch not found")

        # check an integration lswitch is deleted
        lswitch_name = "%s-ls" % name
        for lswitch_id, lswitch in self.fc2._lswitches.iteritems():
            if lswitch['display_name'] == lswitch_name:
                self.fail("Integration switch is not deleted")

    def test_router_delete_after_plugin_restart(self):
        name = 'router1'
        tenant_id = _uuid()
        with self.router(name=name, admin_state_up=True,
                         tenant_id=tenant_id):
            # clear router type cache to mimic plugin restart
            plugin = NeutronManager.get_plugin()
            plugin._router_type = {}

        # check an integration lswitch is deleted
        lswitch_name = "%s-ls" % name
        for lswitch_id, lswitch in self.fc2._lswitches.iteritems():
            if lswitch['display_name'] == lswitch_name:
                self.fail("Integration switch is not deleted")

    def test_router_show(self):
        name = 'router1'
        tenant_id = _uuid()
        expected_value = [('name', name), ('tenant_id', tenant_id),
                          ('admin_state_up', True),
                          ('status', 'PENDING_CREATE'),
                          ('external_gateway_info', None),
                          ('service_router', True)]
        with self.router(name='router1', admin_state_up=True,
                         tenant_id=tenant_id) as router:
            res = self._show('routers', router['router']['id'])
            for k, v in expected_value:
                self.assertEqual(res['router'][k], v)

    def _test_router_create_with_gwinfo_and_l3_ext_net(self, vlan_id=None):
        super(ServiceRouterTestCase,
              self)._test_router_create_with_gwinfo_and_l3_ext_net(
                  vlan_id, validate_ext_gw=False)

    def _test_router_update_gateway_on_l3_ext_net(self, vlan_id=None):
        super(ServiceRouterTestCase,
              self)._test_router_update_gateway_on_l3_ext_net(
                  vlan_id, validate_ext_gw=False)


class TestProxyCreateLswitch(base.BaseTestCase):
    def setUp(self):
        super(TestProxyCreateLswitch, self).setUp()
        self.tenant_id = "foo_tenant"
        self.display_name = "foo_network"
        self.tz_config = [
            {'zone_uuid': 'foo_zone',
             'transport_type': 'stt'}
        ]
        self.tags = [
            {'scope': 'quantum', 'tag': nvplib.NEUTRON_VERSION},
            {'scope': 'os_tid', 'tag': self.tenant_id}
        ]
        self.cluster = None

    def test_create_lswitch_with_basic_args(self):
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config)
        self.assertEqual(self.display_name, result[0])
        self.assertEqual(self.tz_config, result[1])
        self.assertEqual(self.tags, result[2])

    def test_create_lswitch_with_neutron_net_id_as_kwarg(self):
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config,
                                                       neutron_net_id='foo')
        expected = self.tags + [{'scope': 'quantum_net_id', 'tag': 'foo'}]
        self.assertEqual(expected, result[2])

    def test_create_lswitch_with_neutron_net_id_as_arg(self):
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config,
                                                       'foo')
        expected = self.tags + [{'scope': 'quantum_net_id', 'tag': 'foo'}]
        self.assertEqual(expected, result[2])

    def test_create_lswitch_with_shared_as_kwarg(self):
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config,
                                                       shared=True)
        expected = self.tags + [{'scope': 'shared', 'tag': 'true'}]
        self.assertEqual(expected, result[2])

    def test_create_lswitch_with_shared_as_arg(self):
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config,
                                                       'foo',
                                                       True)
        additional_tags = [{'scope': 'quantum_net_id', 'tag': 'foo'},
                           {'scope': 'shared', 'tag': 'true'}]
        expected = self.tags + additional_tags
        self.assertEqual(expected, result[2])

    def test_create_lswitch_with_additional_tags(self):
        more_tags = [{'scope': 'foo_scope', 'tag': 'foo_tag'}]
        result = nsp._process_base_create_lswitch_args(self.cluster,
                                                       self.tenant_id,
                                                       self.display_name,
                                                       self.tz_config,
                                                       tags=more_tags)
        expected = self.tags + more_tags
        self.assertEqual(expected, result[2])
