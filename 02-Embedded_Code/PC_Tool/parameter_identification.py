import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field


class IdentificationError(ValueError):
    pass


@dataclass(frozen=True)
class RsFitConfig:
    min_abs_current_a: float = 0.05
    max_abs_speed_rpm: float = 5.0
    min_valid_levels: int = 4
    min_samples_per_level: int = 3
    trim_fraction: float = 0.1
    level_settle_time_s: float = 0.02
    voltage_model: str = "deadtime"
    min_rs_ohm: float = 0.1
    max_rs_ohm: float = 50.0
    min_r_squared: float = 0.995
    max_rmse_v: float = 0.1
    max_validation_rmse_v: float = 0.1
    max_positive_negative_asymmetry: float = 0.2
    reference_temperature_c: float = 20.0
    copper_temp_coeff_per_c: float = 0.00393
    min_vbus_v: float = 0.0
    max_vbus_v: float = 120.0
    max_abs_pwm_duty: float = 0.98


@dataclass(frozen=True)
class RsFitResult:
    rs_ohm: float
    voltage_offset_v: float
    valid_level_count: int
    sample_count: int
    r_squared: float
    rmse_v: float
    positive_negative_asymmetry: float
    sign_voltage_v: float = 0.0
    rs_at_reference_ohm: float = math.nan
    temperature_c: float = math.nan
    validation_level_count: int = 0
    validation_sample_count: int = 0
    validation_rmse_v: float = math.nan
    rejected_sample_count: int = 0
    rejection_counts: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _RsSample:
    current: float
    voltage: float
    temperature: float | None
    time_s: float | None
    role: str


def estimate_rs(records, config=None):
    config = config or RsFitConfig()
    grouped, rejection_counts = _group_valid_samples(records, config)
    points = []
    validation_points = []
    sample_count = 0
    validation_sample_count = 0

    for samples in grouped.values():
        samples = _drop_settling_samples(samples, config, rejection_counts)
        if len(samples) < config.min_samples_per_level:
            rejection_counts["too_few_samples"] += len(samples)
            continue

        current_values = [sample.current for sample in samples]
        voltage_values = [sample.voltage for sample in samples]
        temperature_values = [sample.temperature for sample in samples if sample.temperature is not None]
        current = _trimmed_mean(current_values, config.trim_fraction)
        voltage = _trimmed_mean(voltage_values, config.trim_fraction)
        if abs(current) >= config.min_abs_current_a:
            temperature = None
            if temperature_values:
                temperature = _trimmed_mean(temperature_values, config.trim_fraction)
            point = (current, voltage, temperature)
            if _level_role(samples) == "validation":
                validation_points.append(point)
                validation_sample_count += len(samples)
            else:
                points.append(point)
                sample_count += len(samples)

    points.sort(key=lambda item: item[0])
    validation_points.sort(key=lambda item: item[0])
    if len(points) < config.min_valid_levels:
        raise IdentificationError("not enough valid current levels for Rs identification")

    fit_points = [(current, voltage) for current, voltage, _temperature in points]
    fit = _fit_voltage_model(fit_points, config.voltage_model)
    rs_ohm = fit["rs_ohm"]
    offset_v = fit["offset_v"]
    sign_voltage_v = fit["sign_voltage_v"]

    predictions = [
        _predict_voltage(current, rs_ohm, offset_v, sign_voltage_v, config.voltage_model)
        for current, _voltage in fit_points
    ]
    voltages = [voltage for _current, voltage in fit_points]
    residuals = [voltage - prediction for voltage, prediction in zip(voltages, predictions)]
    rmse_v = math.sqrt(sum(residual * residual for residual in residuals) / len(residuals))
    r_squared = _r_squared(voltages, residuals)
    asymmetry = _positive_negative_asymmetry(fit_points, rs_ohm)
    temperatures = [
        temperature
        for _current, _voltage, temperature in points + validation_points
        if temperature is not None and math.isfinite(temperature)
    ]
    temperature_c = sum(temperatures) / len(temperatures) if temperatures else config.reference_temperature_c
    rs_at_reference_ohm = _temperature_corrected_rs(rs_ohm, temperature_c, config)
    validation_rmse_v = _validation_rmse(
        validation_points,
        rs_ohm,
        offset_v,
        sign_voltage_v,
        config,
    )

    _validate_fit(rs_ohm, r_squared, rmse_v, asymmetry, config)
    if math.isfinite(validation_rmse_v) and validation_rmse_v > config.max_validation_rmse_v:
        raise IdentificationError("held-out Rs validation residual is above the configured threshold")

    return RsFitResult(
        rs_ohm=rs_ohm,
        voltage_offset_v=offset_v,
        valid_level_count=len(points),
        sample_count=sample_count,
        r_squared=r_squared,
        rmse_v=rmse_v,
        positive_negative_asymmetry=asymmetry,
        sign_voltage_v=sign_voltage_v,
        rs_at_reference_ohm=rs_at_reference_ohm,
        temperature_c=temperature_c,
        validation_level_count=len(validation_points),
        validation_sample_count=validation_sample_count,
        validation_rmse_v=validation_rmse_v,
        rejected_sample_count=sum(rejection_counts.values()),
        rejection_counts=dict(rejection_counts),
    )


def estimate_rs_from_csv(csv_path, config=None):
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        records = list(csv.DictReader(csv_file))
    return estimate_rs(records, config)


def _group_valid_samples(records, config):
    grouped = defaultdict(list)
    rejection_counts = defaultdict(int)
    for index, record in enumerate(records):
        id_valid = _optional_bool(record, "id_valid", "valid", "sample_valid")
        if id_valid is False:
            rejection_counts["id_invalid"] += 1
            continue

        saturated = _optional_bool(
            record,
            "pwm_saturated",
            "duty_saturated",
            "id_saturated",
            "saturated",
        )
        if saturated is True:
            rejection_counts["pwm_saturated"] += 1
            continue

        pwm_duty = _optional_float(record, "pwm_duty", "duty", "duty_ratio")
        if pwm_duty is not None and math.isfinite(pwm_duty) and abs(pwm_duty) > config.max_abs_pwm_duty:
            rejection_counts["pwm_saturated"] += 1
            continue

        current = _optional_float(record, "id_current_meas", "Id", "id")
        voltage = _optional_float(
            record,
            "id_voltage_eff",
            "id_voltage_meas",
            "terminal_voltage",
            "id_voltage_cmd",
            "Ud",
            "ud",
        )
        if current is None or voltage is None:
            rejection_counts["missing_current_or_voltage"] += 1
            continue
        if not math.isfinite(current) or not math.isfinite(voltage):
            rejection_counts["nonfinite"] += 1
            continue
        if abs(current) < config.min_abs_current_a:
            rejection_counts["low_current"] += 1
            continue

        speed = _optional_float(record, "speed", "FluxWm")
        if speed is not None and math.isfinite(speed) and abs(speed) > config.max_abs_speed_rpm:
            rejection_counts["running"] += 1
            continue

        vbus = _optional_float(record, "vbus", "Vbus", "dc_bus_v")
        if vbus is not None and math.isfinite(vbus) and not config.min_vbus_v <= vbus <= config.max_vbus_v:
            rejection_counts["vbus_out_of_range"] += 1
            continue

        temperature = _optional_float(
            record,
            "temperature_c",
            "motor_temperature_c",
            "winding_temperature_c",
            "board_temperature_c",
        )
        time_s = _optional_float(record, "time_s", "time", "timestamp_s")
        role = _record_role(record)
        level = _record_level(record, index)
        grouped[level].append(_RsSample(current, voltage, temperature, time_s, role))
    return grouped, rejection_counts


def _drop_settling_samples(samples, config, rejection_counts):
    if config.level_settle_time_s <= 0.0:
        return samples

    finite_times = [
        sample.time_s
        for sample in samples
        if sample.time_s is not None and math.isfinite(sample.time_s)
    ]
    if not finite_times:
        return samples

    start_time = min(finite_times)
    kept = []
    for sample in samples:
        if sample.time_s is None or not math.isfinite(sample.time_s):
            rejection_counts["missing_time"] += 1
            continue
        if sample.time_s - start_time < config.level_settle_time_s - 1e-12:
            rejection_counts["settling"] += 1
            continue
        kept.append(sample)
    return kept


def _level_role(samples):
    if any(sample.role == "validation" for sample in samples):
        return "validation"
    return "fit"


def _optional_float(record, *keys):
    for key in keys:
        if key in record and record[key] not in ("", None):
            try:
                return float(record[key])
            except (TypeError, ValueError):
                return None
    return None


def _optional_bool(record, *keys):
    for key in keys:
        if key not in record or record[key] in ("", None):
            continue
        value = record[key]
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "y", "valid"):
            return True
        if text in ("0", "false", "no", "n", "invalid"):
            return False
        try:
            return float(text) != 0.0
        except ValueError:
            return None
    return None


def _record_role(record):
    for key in ("id_role", "id_use", "role", "rs_role"):
        if key in record and record[key] not in ("", None):
            text = str(record[key]).strip().lower()
            if text in ("validation", "validate", "holdout", "check"):
                return "validation"
    return "fit"


def _record_level(record, fallback_index):
    for key in ("id_level", "ID_Level"):
        if key in record and record[key] not in ("", None):
            return record[key]

    current_ref = _optional_float(
        record,
        "id_current_ref",
        "Id_ref",
        "id_ref",
        "current_ref",
    )
    if current_ref is not None and math.isfinite(current_ref):
        return round(current_ref, 6)

    return fallback_index


def _trimmed_mean(values, trim_fraction):
    values = sorted(float(value) for value in values)
    if not values:
        raise IdentificationError("cannot average an empty sample set")
    trim_count = int(len(values) * max(0.0, min(0.45, trim_fraction)))
    if trim_count > 0 and len(values) > trim_count * 2:
        values = values[trim_count:-trim_count]
    return sum(values) / len(values)


def _fit_voltage_model(points, voltage_model):
    if voltage_model == "linear_offset":
        params = _least_squares(points, voltage_model)
        return {"rs_ohm": params[0], "offset_v": params[1], "sign_voltage_v": 0.0}
    if voltage_model == "deadtime":
        params = _least_squares(points, voltage_model)
        return {"rs_ohm": params[0], "offset_v": params[1], "sign_voltage_v": params[2]}
    raise IdentificationError(f"unsupported Rs voltage model: {voltage_model}")


def _least_squares(points, voltage_model):
    rows = [_design_row(current, voltage_model) for current, _voltage in points]
    column_count = len(rows[0])
    normal = [[0.0 for _col in range(column_count)] for _row in range(column_count)]
    rhs = [0.0 for _row in range(column_count)]

    for row, (_current, voltage) in zip(rows, points):
        for row_index in range(column_count):
            rhs[row_index] += row[row_index] * voltage
            for col_index in range(column_count):
                normal[row_index][col_index] += row[row_index] * row[col_index]

    return _solve_linear_system(normal, rhs)


def _design_row(current, voltage_model):
    if voltage_model == "linear_offset":
        return [current, 1.0]
    return [current, 1.0, 1.0 if current > 0.0 else -1.0]


def _solve_linear_system(matrix, values):
    size = len(values)
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]

    for pivot_index in range(size):
        pivot_row = max(range(pivot_index, size), key=lambda row: abs(augmented[row][pivot_index]))
        if abs(augmented[pivot_row][pivot_index]) < 1e-12:
            raise IdentificationError("current levels do not excite enough range for Rs fit")
        augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]

        pivot = augmented[pivot_index][pivot_index]
        for col_index in range(pivot_index, size + 1):
            augmented[pivot_index][col_index] /= pivot

        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            for col_index in range(pivot_index, size + 1):
                augmented[row_index][col_index] -= factor * augmented[pivot_index][col_index]

    return [augmented[row_index][size] for row_index in range(size)]


def _predict_voltage(current, rs_ohm, offset_v, sign_voltage_v, voltage_model):
    voltage = rs_ohm * current + offset_v
    if voltage_model == "deadtime":
        voltage += sign_voltage_v * (1.0 if current > 0.0 else -1.0)
    return voltage


def _linear_fit(points):
    count = len(points)
    sum_x = sum(current for current, _voltage in points)
    sum_y = sum(voltage for _current, voltage in points)
    sum_xx = sum(current * current for current, _voltage in points)
    sum_xy = sum(current * voltage for current, voltage in points)
    denominator = count * sum_xx - sum_x * sum_x
    if abs(denominator) < 1e-12:
        raise IdentificationError("current levels do not excite enough range for Rs fit")

    slope = (count * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / count
    return slope, intercept


def _temperature_corrected_rs(rs_ohm, temperature_c, config):
    scale = 1.0 + config.copper_temp_coeff_per_c * (temperature_c - config.reference_temperature_c)
    if scale <= 0.0:
        raise IdentificationError("invalid temperature correction scale for Rs identification")
    return rs_ohm / scale


def _validation_rmse(validation_points, rs_ohm, offset_v, sign_voltage_v, config):
    if not validation_points:
        return math.nan

    validation_fit_points = [
        (current, voltage)
        for current, voltage, _temperature in validation_points
    ]
    predictions = [
        _predict_voltage(current, rs_ohm, offset_v, sign_voltage_v, config.voltage_model)
        for current, _voltage in validation_fit_points
    ]
    residuals = [
        voltage - prediction
        for (_current, voltage), prediction in zip(validation_fit_points, predictions)
    ]
    return math.sqrt(sum(residual * residual for residual in residuals) / len(residuals))


def _validate_fit(rs_ohm, r_squared, rmse_v, positive_negative_asymmetry, config):
    if not config.min_rs_ohm <= rs_ohm <= config.max_rs_ohm:
        raise IdentificationError("Rs estimate is outside the configured valid range")
    if r_squared < config.min_r_squared:
        raise IdentificationError("Rs fit R-squared is below the configured threshold")
    if rmse_v > config.max_rmse_v:
        raise IdentificationError("Rs fit residual is above the configured threshold")
    if positive_negative_asymmetry > config.max_positive_negative_asymmetry:
        raise IdentificationError("positive and negative current levels produce inconsistent Rs")


def _r_squared(voltages, residuals):
    mean_voltage = sum(voltages) / len(voltages)
    total = sum((voltage - mean_voltage) ** 2 for voltage in voltages)
    if total <= 1e-12:
        return 1.0
    residual_total = sum(residual * residual for residual in residuals)
    return 1.0 - residual_total / total


def _positive_negative_asymmetry(points, fitted_rs):
    positive = [(current, voltage) for current, voltage in points if current > 0.0]
    negative = [(current, voltage) for current, voltage in points if current < 0.0]
    if len(positive) < 2 or len(negative) < 2 or abs(fitted_rs) < 1e-12:
        return math.inf

    positive_rs, _ = _linear_fit(positive)
    negative_rs, _ = _linear_fit(negative)
    return abs(positive_rs - negative_rs) / abs(fitted_rs)
