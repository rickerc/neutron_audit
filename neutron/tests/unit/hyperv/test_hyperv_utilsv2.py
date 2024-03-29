# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Cloudbase Solutions SRL
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# @author: Alessandro Pilotti, Cloudbase Solutions Srl

"""
Unit tests for the Hyper-V utils V2.
"""

import mock

from neutron.plugins.hyperv.agent import utils
from neutron.plugins.hyperv.agent import utilsv2
from neutron.tests import base


class TestHyperVUtilsV2(base.BaseTestCase):

    _FAKE_VSWITCH_NAME = "fake_vswitch_name"
    _FAKE_PORT_NAME = "fake_port_name"
    _FAKE_JOB_PATH = 'fake_job_path'
    _FAKE_RET_VAL = 0
    _FAKE_VM_PATH = "fake_vm_path"
    _FAKE_RES_DATA = "fake_res_data"
    _FAKE_RES_PATH = "fake_res_path"
    _FAKE_VSWITCH = "fake_vswitch"
    _FAKE_VLAN_ID = "fake_vlan_id"
    _FAKE_CLASS_NAME = "fake_class_name"
    _FAKE_ELEMENT_NAME = "fake_element_name"
    _FAKE_HYPERV_VM_STATE = 'fake_hyperv_state'

    _FAKE_ACL_ACT = 'fake_acl_action'
    _FAKE_ACL_DIR = 'fake_acl_dir'
    _FAKE_ACL_TYPE = 'fake_acl_type'
    _FAKE_REMOTE_ADDR = '0.0.0.0/0'

    def setUp(self):
        super(TestHyperVUtilsV2, self).setUp()
        self._utils = utilsv2.HyperVUtilsV2()
        self._utils._wmi_conn = mock.MagicMock()

    def test_connect_vnic_to_vswitch_found(self):
        self._test_connect_vnic_to_vswitch(True)

    def test_connect_vnic_to_vswitch_not_found(self):
        self._test_connect_vnic_to_vswitch(False)

    def _test_connect_vnic_to_vswitch(self, found):
        self._utils._get_vnic_settings = mock.MagicMock()

        if not found:
            mock_vm = mock.MagicMock()
            self._utils._get_vm_from_res_setting_data = mock.MagicMock(
                return_value=mock_vm)
            self._utils._add_virt_resource = mock.MagicMock()
        else:
            self._utils._modify_virt_resource = mock.MagicMock()

        self._utils._get_vswitch = mock.MagicMock()
        self._utils._get_switch_port_allocation = mock.MagicMock()

        mock_port = mock.MagicMock()
        self._utils._get_switch_port_allocation.return_value = (mock_port,
                                                                found)

        self._utils.connect_vnic_to_vswitch(self._FAKE_VSWITCH_NAME,
                                            self._FAKE_PORT_NAME)

        if not found:
            self._utils._add_virt_resource.assert_called_with(mock_vm,
                                                              mock_port)
        else:
            self._utils._modify_virt_resource.assert_called_with(mock_port)

    def test_add_virt_resource(self):
        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.AddResourceSettings.return_value = (self._FAKE_JOB_PATH,
                                                     mock.MagicMock(),
                                                     self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        mock_vm = mock.MagicMock()
        mock_vm.path_.return_value = self._FAKE_VM_PATH

        self._utils._check_job_status = mock.MagicMock()

        self._utils._add_virt_resource(mock_vm, mock_res_setting_data)

        mock_svc.AddResourceSettings.assert_called_with(self._FAKE_VM_PATH,
                                                        [self._FAKE_RES_DATA])

    def test_add_virt_feature(self):
        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.AddFeatureSettings.return_value = (self._FAKE_JOB_PATH,
                                                    mock.MagicMock(),
                                                    self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        mock_vm = mock.MagicMock()
        mock_vm.path_.return_value = self._FAKE_VM_PATH

        self._utils._check_job_status = mock.MagicMock()

        self._utils._add_virt_feature(mock_vm, mock_res_setting_data)

        mock_svc.AddFeatureSettings.assert_called_once_with(
            self._FAKE_VM_PATH, [self._FAKE_RES_DATA])

    def test_modify_virt_resource(self):
        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.ModifyResourceSettings.return_value = (self._FAKE_JOB_PATH,
                                                        mock.MagicMock(),
                                                        self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        self._utils._check_job_status = mock.MagicMock()

        self._utils._modify_virt_resource(mock_res_setting_data)

        mock_svc.ModifyResourceSettings.assert_called_with(
            ResourceSettings=[self._FAKE_RES_DATA])

    def test_remove_virt_resource(self):
        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.RemoveResourceSettings.return_value = (self._FAKE_JOB_PATH,
                                                        self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.path_.return_value = self._FAKE_RES_PATH

        self._utils._check_job_status = mock.MagicMock()

        self._utils._remove_virt_resource(mock_res_setting_data)

        mock_svc.RemoveResourceSettings.assert_called_with(
            ResourceSettings=[self._FAKE_RES_PATH])

    def test_disconnect_switch_port_delete_port(self):
        self._test_disconnect_switch_port(True)

    def test_disconnect_switch_port_modify_port(self):
        self._test_disconnect_switch_port(False)

    def _test_disconnect_switch_port(self, delete_port):
        self._utils._get_switch_port_allocation = mock.MagicMock()

        mock_sw_port = mock.MagicMock()
        self._utils._get_switch_port_allocation.return_value = (mock_sw_port,
                                                                True)

        if delete_port:
            self._utils._remove_virt_resource = mock.MagicMock()
        else:
            self._utils._modify_virt_resource = mock.MagicMock()

        self._utils.disconnect_switch_port(self._FAKE_VSWITCH_NAME,
                                           self._FAKE_PORT_NAME,
                                           delete_port)

        if delete_port:
            self._utils._remove_virt_resource.assert_called_with(mock_sw_port)
        else:
            self._utils._modify_virt_resource.assert_called_with(mock_sw_port)

    def test_get_vswitch(self):
        self._utils._conn.Msvm_VirtualEthernetSwitch.return_value = [
            self._FAKE_VSWITCH]
        vswitch = self._utils._get_vswitch(self._FAKE_VSWITCH_NAME)

        self.assertEqual(self._FAKE_VSWITCH, vswitch)

    def test_get_vswitch_not_found(self):
        self._utils._conn.Msvm_VirtualEthernetSwitch.return_value = []
        self.assertRaises(utils.HyperVException, self._utils._get_vswitch,
                          self._FAKE_VSWITCH_NAME)

    def test_get_vswitch_external_port(self):
        mock_vswitch = mock.MagicMock()
        mock_sw_port = mock.MagicMock()
        mock_vswitch.associators.return_value = [mock_sw_port]
        mock_le = mock_sw_port.associators.return_value
        mock_le.__len__.return_value = 1
        mock_le1 = mock_le[0].associators.return_value
        mock_le1.__len__.return_value = 1

        vswitch_port = self._utils._get_vswitch_external_port(mock_vswitch)

        self.assertEqual(mock_sw_port, vswitch_port)

    def test_set_vswitch_port_vlan_id(self):
        mock_port_alloc = mock.MagicMock()
        self._utils._get_switch_port_allocation = mock.MagicMock(return_value=(
            mock_port_alloc, True))
        self._utils._get_vlan_setting_data_from_port_alloc = mock.MagicMock()

        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.RemoveFeatureSettings.return_value = (self._FAKE_JOB_PATH,
                                                       self._FAKE_RET_VAL)
        mock_vlan_settings = mock.MagicMock()
        self._utils._get_vlan_setting_data = mock.MagicMock(return_value=(
            mock_vlan_settings, True))

        mock_svc.AddFeatureSettings.return_value = (self._FAKE_JOB_PATH,
                                                    None,
                                                    self._FAKE_RET_VAL)

        self._utils.set_vswitch_port_vlan_id(self._FAKE_VLAN_ID,
                                             self._FAKE_PORT_NAME)

        self.assertTrue(mock_svc.RemoveFeatureSettings.called)
        self.assertTrue(mock_svc.AddFeatureSettings.called)

    def test_get_setting_data(self):
        self._utils._get_first_item = mock.MagicMock(return_value=None)

        mock_data = mock.MagicMock()
        self._utils._get_default_setting_data = mock.MagicMock(
            return_value=mock_data)

        ret_val = self._utils._get_setting_data(self._FAKE_CLASS_NAME,
                                                self._FAKE_ELEMENT_NAME,
                                                True)

        self.assertEqual(ret_val, (mock_data, False))

    def test_enable_port_metrics_collection(self):
        mock_port = mock.MagicMock()
        self._utils._get_switch_port_allocation = mock.MagicMock(return_value=(
            mock_port, True))

        mock_acl = mock.MagicMock()

        with mock.patch.multiple(
            self._utils,
            _get_default_setting_data=mock.MagicMock(return_value=mock_acl),
            _add_virt_feature=mock.MagicMock()):

            self._utils.enable_port_metrics_collection(self._FAKE_PORT_NAME)

            self.assertEqual(4, len(self._utils._add_virt_feature.mock_calls))
            self._utils._add_virt_feature.assert_called_with(
                mock_port, mock_acl)

    def test_filter_acls(self):
        mock_acl = mock.MagicMock()
        mock_acl.Action = self._FAKE_ACL_ACT
        mock_acl.Applicability = self._utils._ACL_APPLICABILITY_LOCAL
        mock_acl.Direction = self._FAKE_ACL_DIR
        mock_acl.AclType = self._FAKE_ACL_TYPE
        mock_acl.RemoteAddress = self._FAKE_REMOTE_ADDR

        acls = [mock_acl, mock_acl]
        good_acls = self._utils._filter_acls(
            acls, self._FAKE_ACL_ACT, self._FAKE_ACL_DIR,
            self._FAKE_ACL_TYPE, self._FAKE_REMOTE_ADDR)
        bad_acls = self._utils._filter_acls(
            acls, self._FAKE_ACL_ACT, self._FAKE_ACL_DIR, self._FAKE_ACL_TYPE)

        self.assertEqual(acls, good_acls)
        self.assertEqual([], bad_acls)

    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._get_switch_port_allocation')
    def test_enable_control_metrics_ok(self, mock_get_port_allocation):
        mock_metrics_svc = self._utils._conn.Msvm_MetricService()[0]
        mock_metrics_def_source = self._utils._conn.CIM_BaseMetricDefinition
        mock_metric_def = mock.MagicMock()
        mock_port = mock.MagicMock()
        mock_get_port_allocation.return_value = (mock_port, True)

        mock_metrics_def_source.return_value = [mock_metric_def]
        m_call = mock.call(Subject=mock_port.path_.return_value,
                           Definition=mock_metric_def.path_.return_value,
                           MetricCollectionEnabled=self._utils._METRIC_ENABLED)

        self._utils.enable_control_metrics(self._FAKE_PORT_NAME)

        mock_metrics_svc.ControlMetrics.assert_has_calls([m_call, m_call])

    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._get_switch_port_allocation')
    def test_enable_control_metrics_no_port(self, mock_get_port_allocation):
        mock_metrics_svc = self._utils._conn.Msvm_MetricService()[0]
        mock_get_port_allocation.return_value = (None, False)

        self._utils.enable_control_metrics(self._FAKE_PORT_NAME)
        self.assertEqual(0, mock_metrics_svc.ControlMetrics.call_count)

    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._get_switch_port_allocation')
    def test_enable_control_metrics_no_def(self, mock_get_port_allocation):
        mock_metrics_svc = self._utils._conn.Msvm_MetricService()[0]
        mock_metrics_def_source = self._utils._conn.CIM_BaseMetricDefinition
        mock_port = mock.MagicMock()

        mock_get_port_allocation.return_value = (mock_port, True)
        mock_metrics_def_source.return_value = None

        self._utils.enable_control_metrics(self._FAKE_PORT_NAME)
        self.assertEqual(0, mock_metrics_svc.ControlMetrics.call_count)

    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._is_port_vm_started')
    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._get_switch_port_allocation')
    def test_can_enable_control_metrics_true(self, mock_get, mock_is_started):
        mock_acl = mock.MagicMock()
        mock_acl.Action = self._utils._ACL_ACTION_METER
        self._test_can_enable_control_metrics(mock_get, mock_is_started,
                                              [mock_acl, mock_acl], True)

    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._is_port_vm_started')
    @mock.patch('neutron.plugins.hyperv.agent.utilsv2.HyperVUtilsV2'
                '._get_switch_port_allocation')
    def test_can_enable_control_metrics_false(self, mock_get, mock_is_started):
        self._test_can_enable_control_metrics(mock_get, mock_is_started, [],
                                              False)

    def _test_can_enable_control_metrics(self, mock_get_port, mock_vm_started,
                                         acls, expected_result):
        mock_port = mock.MagicMock()
        mock_acl = mock.MagicMock()
        mock_acl.Action = self._utils._ACL_ACTION_METER

        mock_port.associators.return_value = acls
        mock_get_port.return_value = (mock_port, True)
        mock_vm_started.return_value = True

        result = self._utils.can_enable_control_metrics(self._FAKE_PORT_NAME)
        self.assertEqual(expected_result, result)

    def test_is_port_vm_started_true(self):
        self._test_is_port_vm_started(self._utils._HYPERV_VM_STATE_ENABLED,
                                      True)

    def test_is_port_vm_started_false(self):
        self._test_is_port_vm_started(self._FAKE_HYPERV_VM_STATE, False)

    def _test_is_port_vm_started(self, vm_state, expected_result):
        mock_svc = self._utils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_port = mock.MagicMock()
        mock_vmsettings = mock.MagicMock()
        mock_summary = mock.MagicMock()
        mock_summary.EnabledState = vm_state
        mock_vmsettings.path_.return_value = self._FAKE_RES_PATH

        mock_port.associators.return_value = [mock_vmsettings]
        mock_svc.GetSummaryInformation.return_value = (self._FAKE_RET_VAL,
                                                       [mock_summary])

        result = self._utils._is_port_vm_started(mock_port)
        self.assertEqual(expected_result, result)
        mock_svc.GetSummaryInformation.assert_called_once_with(
            [self._utils._VM_SUMMARY_ENABLED_STATE],
            [self._FAKE_RES_PATH])
