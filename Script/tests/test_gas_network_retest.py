# Copyright byteyang. All Rights Reserved.
"""诊断用例的必需技能与负向测试目标分开声明。"""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("gas_network_retest", Path(__file__).parents[1] / "gas_network_retest.py")
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)


class DiagnosticCaseTests(unittest.TestCase):
    def test_required_abilities_match_scenario_and_owning_endpoints(self):
        endpoints = {role: {"Url": f"http://127.0.0.1:{45010 + index}/stream"}
                     for index, role in enumerate(("Server", "Owner", "Observer"))}
        for scenario in ("NotGranted", "MissingRequired", "Blocked", "Cost", "Cooldown", "PredictionRejected", "Success", "ServerOnly"):
            ability = sample.SERVER_ABILITY if scenario == "ServerOnly" else sample.ABILITY
            case = sample.build_case(endpoints, scenario, ability)
            expected = sample.SERVER_ABILITY if scenario in ("MissingRequired", "Blocked", "Cost", "Cooldown", "ServerOnly") else sample.ABILITY
            self.assertEqual({item["Endpoint"] for item in case["RequiredAbilities"]}, {"Server", "Owner"})
            self.assertTrue(all(item["AbilityPath"] == expected for item in case["RequiredAbilities"]))
            if scenario == "NotGranted":
                attempted = next(step for step in case["Steps"] if step["Id"] == "attempt")
                self.assertNotEqual(attempted["Arguments"]["AbilityPath"], expected)


if __name__ == "__main__":
    unittest.main()
