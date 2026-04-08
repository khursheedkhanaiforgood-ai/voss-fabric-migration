"""Unit tests for SwitchModel and LabState."""
import pytest
from ..models.switch_state import SwitchModel, VlanConfig, SwitchOS
from ..models.lab_state import LabState
from ..config import SPBM


class TestSwitchModel:

    def test_initial_state_is_exos(self):
        sw = SwitchModel(switch_id="SW1", system_id="0000.0000.0001", nick_name="0.00.01")
        assert sw.os == SwitchOS.EXOS
        assert not sw.isis_enabled
        assert not sw.fabric_ready

    def test_fabric_ready_requires_all_three(self):
        sw = SwitchModel(switch_id="SW1", system_id="0000.0000.0001", nick_name="0.00.01")
        sw.isis_configured = True
        sw.isis_system_id = "0000.0000.0001"
        sw.isis_manual_area = "00.0001"
        sw.isis_enabled = True
        # spbm not yet configured
        assert not sw.fabric_ready
        sw.spbm_configured = True
        sw.spbm_ethertype = "0x8100"
        sw.spbm_nick_name = "0.00.01"
        # nni not yet ready
        assert not sw.fabric_ready
        sw.nni_isis_enabled = True
        sw.nni_no_shutdown = True
        assert sw.fabric_ready

    def test_vlans_with_isids(self):
        sw = SwitchModel(switch_id="SW1", system_id="0000.0000.0001", nick_name="0.00.01")
        sw.vlans[20] = VlanConfig(vlan_id=20, name="Alpha", isid=100020)
        sw.vlans[30] = VlanConfig(vlan_id=30, name="Bravo")
        assert 20 in sw.vlans_with_isids
        assert 30 not in sw.vlans_with_isids


class TestLabState:

    def test_adjacency_down_initially(self):
        lab = LabState()
        assert not lab.isis_adjacency_up

    def test_adjacency_up_when_both_ready(self):
        lab = LabState()
        for sw in (lab.sw1, lab.sw2):
            sw.isis_configured = True
            sw.isis_manual_area = "00.0001"
            sw.isis_enabled = True
            sw.spbm_configured = True
            sw.spbm_ethertype = "0x8100"
            sw.spbm_nick_name = sw.nick_name
            sw.nni_isis_enabled = True
            sw.nni_no_shutdown = True
        lab.sw1.isis_system_id = "0000.0000.0001"
        lab.sw2.isis_system_id = "0000.0000.0002"
        assert lab.isis_adjacency_up

    def test_adjacency_down_on_ethertype_mismatch(self):
        lab = LabState()
        for sw in (lab.sw1, lab.sw2):
            sw.isis_configured = True
            sw.isis_manual_area = "00.0001"
            sw.isis_enabled = True
            sw.spbm_configured = True
            sw.nni_isis_enabled = True
            sw.nni_no_shutdown = True
        lab.sw1.isis_system_id = "0000.0000.0001"
        lab.sw2.isis_system_id = "0000.0000.0002"
        lab.sw1.spbm_ethertype = "0x8100"
        lab.sw2.spbm_ethertype = "0x88a8"  # MISMATCH
        assert not lab.isis_adjacency_up
        reason = lab.adjacency_failure_reason()
        assert "ethertype" in reason.lower()

    def test_adjacency_failure_reason_system_id_conflict(self):
        lab = LabState()
        lab.sw1.isis_system_id = "0000.0000.0001"
        lab.sw2.isis_system_id = "0000.0000.0001"  # same
        lab.sw1.isis_enabled = True
        lab.sw2.isis_enabled = True
        lab.sw1.spbm_ethertype = "0x8100"
        lab.sw2.spbm_ethertype = "0x8100"
        lab.sw1.isis_manual_area = "00.0001"
        lab.sw2.isis_manual_area = "00.0001"
        lab.sw1.nni_isis_enabled = True
        lab.sw1.nni_no_shutdown = True
        lab.sw2.nni_isis_enabled = True
        lab.sw2.nni_no_shutdown = True
        lab.sw1.isis_configured = True
        lab.sw2.isis_configured = True
        lab.sw1.spbm_configured = True
        lab.sw2.spbm_configured = True
        lab.sw1.spbm_nick_name = "0.00.01"
        lab.sw2.spbm_nick_name = "0.00.01"
        assert not lab.isis_adjacency_up
        reason = lab.adjacency_failure_reason()
        assert "conflict" in reason.lower()
