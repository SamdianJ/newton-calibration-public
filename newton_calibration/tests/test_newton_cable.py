# SPDX-FileCopyrightText: Copyright (c) 2026 The Newton Developers
# SPDX-License-Identifier: Apache-2.0

"""Exercise cable adapters with the optional Newton runtime and SLS patch."""

import importlib
import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

from newton_calibration import Experiment, Template

CASE = Path(__file__).resolve().parents[2] / "examples" / "cable_calibration"
HAS_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ("newton", "scipy"))


@unittest.skipUnless(HAS_RUNTIME, "install the newton and cable extras")
class TestNewtonCable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import newton

        builder = newton.ModelBuilder()
        newton.solvers.SolverVBD.register_custom_attributes(builder)
        cls.has_sls = "vbd:visco_bend_ke" in builder.custom_attributes

    def _case(self, stage):
        config = json.loads((CASE / "configs" / f"{stage}.json").read_text())
        # Short CPU checks exercise construction and stepping, not qualification.
        config["template"]["numeric_settings"].update(device="cpu", iterations=2, dynamic_iterations=2, block_steps=2)
        config["template"]["discretization"]["segments"] = 4
        template = Template(**config["template"])
        parameters = {entry["name"]: entry["baseline"] for entry in config["parameters"]}
        package = "examples.cable_calibration.backends." + ("b" if stage == "Bstar" else stage.lower())
        backend = importlib.import_module(package + (".sls_backend" if stage == "C" else ".newton_backend"))
        asset_type = backend.SLSCableAsset if stage == "C" else backend.CableAsset
        asset = asset_type(parameters, config=config["asset_config"])
        rollout = importlib.import_module(package + ".rollout").NewtonRollout
        return asset, template, parameters, rollout

    def _check_bindings(self, stage):
        asset, template, parameters, _ = self._case(stage)
        expected = {**template.fixed_parameters, **parameters}
        for experiment_id in ("noplug_left", "noplug_release", "withplug_left", "withplug_release"):
            with self.subTest(stage=stage, experiment=experiment_id):
                env = asset.create_environment(template, expected, template.experiment_settings[experiment_id])
                try:
                    for name, value in expected.items():
                        self.assertAlmostEqual(env.applied_parameters[name], value, delta=max(abs(value) * 2e-6, 2e-5))
                    slots = env.model.joint_qd_start.numpy()[env.joints[: env.n]]
                    coefficients = env.model.joint_target_ke.numpy()
                    np.testing.assert_allclose(coefficients[slots + 3], coefficients[slots + 4])
                    np.testing.assert_allclose(
                        coefficients[slots + 2], expected["stretch_stiffness"] * (env.length / 32) / env.h
                    )
                    if stage == "C" and experiment_id.endswith("release"):
                        self.assertTrue(env.solver.enable_viscoelasticity)
                        self.assertGreater(np.linalg.norm(env.solver.joint_visco_moment_prev.numpy()), 0.0)
                finally:
                    env.close()

    def _check_batch(self, stage):
        asset, template, parameters, rollout = self._case(stage)
        times = np.array([0.0, template.numeric_settings["dt"], 2.0 * template.numeric_settings["dt"]])
        experiment = Experiment("noplug_release", "release", np.zeros((3, 30)), times=times)
        name = next(iter(parameters))
        perturbed = {**parameters, name: parameters[name] * 1.2}
        trials = [("baseline", parameters), ("perturbed", perturbed)]
        serial = rollout(capacity=1).execute_batch(template, asset, trials, [experiment])
        packed = rollout(capacity=2).execute_batch(template, asset, trials, [experiment])
        for expected, actual in zip(serial, packed, strict=True):
            with self.subTest(stage=stage, trial=expected.trial_id):
                self.assertEqual(expected.status, "completed", expected.error)
                self.assertEqual(actual.status, "completed", actual.error)
                self.assertEqual(actual.key, expected.key)
                np.testing.assert_array_equal(actual.trace.times, times)
                np.testing.assert_allclose(actual.trace.values, expected.trace.values, atol=2e-6, rtol=2e-6)
                self.assertTrue(np.isfinite(actual.trace.positions).all())
                for name, value in expected.applied_parameters.items():
                    self.assertAlmostEqual(actual.applied_parameters[name], value, delta=max(abs(value) * 2e-6, 2e-5))

    def test_vbd_bindings(self):
        """Read physical coefficients from the six-DOF rods, including the clamp and plug."""
        for stage in ("A", "B", "Bstar"):
            self._check_bindings(stage)

    def test_vbd_batch_matches_serial(self):
        """Match independent and packed dynamic traces for two distinct candidates."""
        for stage in ("A", "B", "Bstar"):
            self._check_batch(stage)

    def test_sls_bindings_and_batch(self):
        """Preserve measured material history and candidate isolation in the SLS adapter."""
        if not self.has_sls:
            self.skipTest("apply the cable SLS patch to Newton")
        self._check_bindings("C")
        self._check_batch("C")


if __name__ == "__main__":
    unittest.main(verbosity=2)
