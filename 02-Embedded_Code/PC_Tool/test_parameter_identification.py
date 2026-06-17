import unittest
import tempfile
from pathlib import Path

from parameter_identification import (
    IdentificationError,
    RsFitConfig,
    estimate_rs,
    estimate_rs_from_csv,
)


class RsIdentificationTest(unittest.TestCase):
    def make_records(self, levels, rs=6.97, offset=0.32, repeats=8):
        records = []
        for level_index, current in enumerate(levels):
            for sample_index in range(repeats):
                ripple = (sample_index - repeats / 2) * 0.0005
                measured_current = current + ripple
                records.append(
                    {
                        "id_level": level_index,
                        "id_current_meas": measured_current,
                        "id_voltage_cmd": rs * measured_current + offset,
                        "speed": 0.2,
                    }
                )
        return records

    def test_estimates_rs_slope_with_voltage_offset(self):
        records = self.make_records([-0.6, -0.4, -0.25, 0.25, 0.4, 0.6])

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertAlmostEqual(result.voltage_offset_v, 0.32, places=3)
        self.assertEqual(result.valid_level_count, 6)
        self.assertGreater(result.r_squared, 0.999)

    def test_filters_low_current_and_running_samples_before_fit(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        records.extend(
            [
                {
                    "id_level": 99,
                    "id_current_meas": 0.01,
                    "id_voltage_cmd": 30.0,
                    "speed": 0.0,
                },
                {
                    "id_level": 100,
                    "id_current_meas": 0.8,
                    "id_voltage_cmd": 40.0,
                    "speed": 120.0,
                },
            ]
        )

        result = estimate_rs(records, RsFitConfig(max_abs_speed_rpm=5.0))

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.valid_level_count, 4)

    def test_discards_settling_samples_and_invalid_flags(self):
        records = []
        for level_index, current in enumerate([-0.6, -0.4, 0.4, 0.6]):
            for sample_index in range(8):
                measured_current = current + sample_index * 0.0002
                voltage = 6.97 * measured_current + 0.32
                if sample_index < 4:
                    voltage += 0.8
                records.append(
                    {
                        "time_s": level_index * 0.1 + sample_index * 0.005,
                        "id_level": level_index,
                        "id_current_meas": measured_current,
                        "id_voltage_cmd": voltage,
                        "id_valid": 1,
                        "speed": 0.2,
                    }
                )
        records.append(
            {
                "time_s": 1.0,
                "id_level": 99,
                "id_current_meas": 0.8,
                "id_voltage_cmd": 80.0,
                "id_valid": 0,
                "speed": 0.2,
            }
        )

        result = estimate_rs(records, RsFitConfig(level_settle_time_s=0.02))

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.sample_count, 16)
        self.assertEqual(result.rejection_counts["settling"], 16)
        self.assertEqual(result.rejection_counts["id_invalid"], 1)

    def test_rejects_pwm_saturated_samples(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        for sample_index in range(8):
            records.append(
                {
                    "id_level": 77,
                    "id_current_meas": 0.9,
                    "id_voltage_cmd": 40.0,
                    "pwm_saturated": 1,
                    "speed": 0.1,
                }
            )

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.valid_level_count, 4)
        self.assertEqual(result.rejection_counts["pwm_saturated"], 8)

    def test_groups_untagged_records_by_current_reference(self):
        records = []
        for current in [-0.6, -0.4, 0.4, 0.6]:
            for sample_index in range(8):
                measured_current = current + sample_index * 0.0002
                records.append(
                    {
                        "Id_ref": current,
                        "Id": measured_current,
                        "Ud": 6.97 * measured_current + 0.32,
                        "FluxWm": 0.1,
                    }
                )

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.valid_level_count, 4)
        self.assertEqual(result.sample_count, 32)

    def test_estimates_rs_without_deadtime_bias(self):
        records = self.make_records([-0.7, -0.45, -0.25, 0.25, 0.45, 0.7])
        for record in records:
            current = record["id_current_meas"]
            record["id_voltage_cmd"] = 6.97 * current + 0.32 + 0.18 * (1 if current > 0 else -1)

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertAlmostEqual(result.voltage_offset_v, 0.32, places=3)
        self.assertAlmostEqual(result.sign_voltage_v, 0.18, places=3)

    def test_prefers_effective_voltage_over_command_voltage(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        for record in records:
            current = record["id_current_meas"]
            record["id_voltage_eff"] = 6.97 * current + 0.32
            record["id_voltage_cmd"] = 9.0 * current + 1.0

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertAlmostEqual(result.voltage_offset_v, 0.32, places=3)

    def test_reports_rs_at_reference_temperature(self):
        reference_rs = 6.97
        measured_temperature = 60.0
        copper_alpha = 0.00393
        hot_rs = reference_rs * (1 + copper_alpha * (measured_temperature - 20.0))
        records = self.make_records([-0.6, -0.4, 0.4, 0.6], rs=hot_rs)
        for record in records:
            record["temperature_c"] = measured_temperature

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, hot_rs, places=3)
        self.assertAlmostEqual(result.rs_at_reference_ohm, reference_rs, places=3)
        self.assertAlmostEqual(result.temperature_c, measured_temperature, places=3)

    def test_rejects_excessive_fit_residual(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        for record in records:
            if record["id_level"] == 2:
                record["id_voltage_cmd"] += 0.5

        with self.assertRaises(IdentificationError):
            estimate_rs(records, RsFitConfig(max_rmse_v=0.05))

    def test_uses_holdout_levels_for_validation_only(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        validation_records = self.make_records([0.5], repeats=6)
        for record in validation_records:
            record["id_level"] = 200
            record["id_role"] = "validation"
        records.extend(validation_records)

        result = estimate_rs(records)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.valid_level_count, 4)
        self.assertEqual(result.validation_level_count, 1)
        self.assertEqual(result.validation_sample_count, 6)
        self.assertLess(result.validation_rmse_v, 0.001)

    def test_rejects_bad_holdout_validation(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        validation_records = self.make_records([0.5], repeats=6)
        for record in validation_records:
            record["id_level"] = 200
            record["id_role"] = "validation"
            record["id_voltage_cmd"] += 0.4
        records.extend(validation_records)

        with self.assertRaises(IdentificationError):
            estimate_rs(records, RsFitConfig(max_validation_rmse_v=0.05))

    def test_rejects_when_not_enough_valid_current_levels(self):
        records = self.make_records([0.25, 0.4])

        with self.assertRaises(IdentificationError):
            estimate_rs(records)

    def test_estimates_rs_from_csv_file(self):
        records = self.make_records([-0.6, -0.4, 0.4, 0.6])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "rs_capture.csv"
            csv_path.write_text(
                "id_level,id_current_meas,id_voltage_cmd,speed\n"
                + "\n".join(
                    f"{row['id_level']},{row['id_current_meas']},{row['id_voltage_cmd']},{row['speed']}"
                    for row in records
                ),
                encoding="utf-8",
            )

            result = estimate_rs_from_csv(csv_path)

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertEqual(result.valid_level_count, 4)


if __name__ == "__main__":
    unittest.main()
