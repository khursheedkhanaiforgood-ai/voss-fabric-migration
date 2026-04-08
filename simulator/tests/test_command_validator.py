"""Unit tests for CommandValidatorService."""
import pytest
from ..services.command_validator import CommandValidatorService
from ..models.migration_step import get_step


class TestCommandValidator:

    def setup_method(self):
        self.v = CommandValidatorService()

    def test_exact_match_isis(self):
        step = get_step(4)  # config_isis
        result = self.v.validate("router isis", step, "SW1", 0)
        assert result.valid
        assert result.match_type == "exact"

    def test_wrong_system_id(self):
        step = get_step(4)
        result = self.v.validate("system-id 0000.0000.0099", step, "SW1", 1)
        assert not result.valid
        assert result.match_type == "partial"
        assert "system-id" in result.feedback.lower()

    def test_ethertype_mismatch_hint(self):
        step = get_step(5)  # config_spbm
        result = self.v.validate("ethertype 0x88a8", step, "SW1", 2)
        assert not result.valid
        assert "ethertype" in result.feedback.lower()
        assert "0x8100" in result.feedback

    def test_save_config_exos_habit(self):
        step = get_step(15)  # save_config
        result = self.v.validate("save configuration", step, "SW1", 0)
        assert not result.valid
        assert "EXOS" in result.feedback

    def test_enable_ipforwarding_exos_habit(self):
        step = get_step(10)  # config_iface_vlans
        result = self.v.validate("enable ipforwarding vlan Alpha", step, "SW1", 0)
        assert not result.valid
        assert "ipforwarding" in result.feedback.lower() or "VOSS" in result.feedback

    def test_vlan_isid_convention(self):
        step = get_step(9)  # assign_isids — first command is VLAN 10
        result = self.v.validate("vlan i-sid 10 100010", step, "SW1", 0)
        assert result.valid

    def test_wrong_isid(self):
        step = get_step(9)
        result = self.v.validate("vlan i-sid 20 200020", step, "SW1", 0)
        assert not result.valid
        assert "i-sid" in result.feedback.lower()

    def test_default_route_correct(self):
        step = get_step(13)  # config_internet
        cmds = step.expected_commands["SW1"]
        # find the ip route command index
        for i, c in enumerate(cmds):
            if c.startswith("ip route"):
                result = self.v.validate(c, step, "SW1", i)
                assert result.valid
                break

    def test_state_updates_on_router_isis_enable(self):
        step = get_step(6)  # enable_isis
        result = self.v.validate("router isis enable", step, "SW1", 0)
        assert result.valid
        assert result.state_updates.get("isis_enabled") is True
