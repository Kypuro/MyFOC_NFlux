function result = estimatePmsmRs(data, config)
%estimatePmsmRs Estimate PMSM stator resistance from standstill ID data.
%
%   result = estimatePmsmRs(data) accepts a table or CSV file path. The
%   estimator expects a locked/stopped motor and multiple positive/negative
%   current levels. It fits:
%
%       V = Rs * I + b0 + bsign * sign(I)
%
%   The sign-dependent voltage term keeps inverter dead-time and device-drop
%   errors from being folded into the resistance slope.

if nargin < 2
    config = struct();
end

config = applyDefaultConfig(config);
data = readInputTable(data);
[groups, rejections] = groupValidSamples(data, config);
[fitPoints, validationPoints, sampleCount, validationSampleCount, rejections] = ...
    reduceGroups(groups, config, rejections);

if size(fitPoints, 1) < config.MinValidLevels
    error('estimatePmsmRs:notEnoughLevels', ...
        'Not enough valid current levels for Rs identification.');
end

[rsOhm, offsetV, signVoltageV] = fitVoltageModel(fitPoints, config);
prediction = predictVoltage(fitPoints(:, 1), rsOhm, offsetV, signVoltageV, config);
residual = fitPoints(:, 2) - prediction;
rmseV = sqrt(mean(residual.^2));
rSquared = computeRSquared(fitPoints(:, 2), residual);
asymmetry = computePositiveNegativeAsymmetry(fitPoints, rsOhm);
temperatureC = meanFiniteOrDefault([fitPoints(:, 3); validationPoints(:, 3)], ...
    config.ReferenceTemperatureC);
rsAtReferenceOhm = temperatureCorrectRs(rsOhm, temperatureC, config);
validationRmseV = computeValidationRmse(validationPoints, rsOhm, offsetV, signVoltageV, config);

validateFit(rsOhm, rSquared, rmseV, asymmetry, config);
if isfinite(validationRmseV) && validationRmseV > config.MaxValidationRmseV
    error('estimatePmsmRs:validationResidual', ...
        'Held-out Rs validation residual is above the configured threshold.');
end

result = struct();
result.RsOhm = rsOhm;
result.RsAtReferenceOhm = rsAtReferenceOhm;
result.VoltageOffsetV = offsetV;
result.SignVoltageV = signVoltageV;
result.ValidLevelCount = size(fitPoints, 1);
result.SampleCount = sampleCount;
result.RSquared = rSquared;
result.RmseV = rmseV;
result.PositiveNegativeAsymmetry = asymmetry;
result.TemperatureC = temperatureC;
result.ValidationLevelCount = size(validationPoints, 1);
result.ValidationSampleCount = validationSampleCount;
result.ValidationRmseV = validationRmseV;
result.RejectedSampleCount = sum(struct2array(rejections));
result.RejectionCounts = rejections;
end

function config = applyDefaultConfig(config)
defaults = struct( ...
    'MinAbsCurrentA', 0.05, ...
    'MaxAbsSpeedRpm', 5.0, ...
    'MinValidLevels', 4, ...
    'MinSamplesPerLevel', 3, ...
    'TrimFraction', 0.1, ...
    'LevelSettleTimeS', 0.02, ...
    'VoltageModel', "deadtime", ...
    'MinRsOhm', 0.1, ...
    'MaxRsOhm', 50.0, ...
    'MinRSquared', 0.995, ...
    'MaxRmseV', 0.1, ...
    'MaxValidationRmseV', 0.1, ...
    'MaxPositiveNegativeAsymmetry', 0.2, ...
    'ReferenceTemperatureC', 20.0, ...
    'CopperTempCoeffPerC', 0.00393, ...
    'MinVbusV', 0.0, ...
    'MaxVbusV', 120.0, ...
    'MaxAbsPwmDuty', 0.98);

names = fieldnames(defaults);
for index = 1:numel(names)
    name = names{index};
    if ~isfield(config, name) || isempty(config.(name))
        config.(name) = defaults.(name);
    end
end
end

function data = readInputTable(data)
if istable(data)
    return;
end

if isstring(data) || ischar(data)
    data = readtable(data);
    return;
end

error('estimatePmsmRs:invalidInput', 'Input must be a table or CSV file path.');
end

function rejections = emptyRejectionCounts()
rejections = struct( ...
    'id_invalid', 0, ...
    'pwm_saturated', 0, ...
    'missing_current_or_voltage', 0, ...
    'nonfinite', 0, ...
    'low_current', 0, ...
    'running', 0, ...
    'vbus_out_of_range', 0, ...
    'missing_time', 0, ...
    'settling', 0, ...
    'too_few_samples', 0);
end

function [groups, rejections] = groupValidSamples(data, config)
rejections = emptyRejectionCounts();
groups = struct('key', {}, 'current', {}, 'voltage', {}, 'temperature', {}, 'time', {}, 'role', {});

for row = 1:height(data)
    idValid = optionalBool(data, row, {'id_valid', 'valid', 'sample_valid'});
    if ~isnan(idValid) && ~idValid
        rejections.id_invalid = rejections.id_invalid + 1;
        continue;
    end

    saturated = optionalBool(data, row, {'pwm_saturated', 'duty_saturated', 'id_saturated', 'saturated'});
    if ~isnan(saturated) && saturated
        rejections.pwm_saturated = rejections.pwm_saturated + 1;
        continue;
    end

    pwmDuty = optionalNumber(data, row, {'pwm_duty', 'duty', 'duty_ratio'});
    if isfinite(pwmDuty) && abs(pwmDuty) > config.MaxAbsPwmDuty
        rejections.pwm_saturated = rejections.pwm_saturated + 1;
        continue;
    end

    current = optionalNumber(data, row, {'id_current_meas', 'Id', 'id'});
    voltage = optionalNumber(data, row, {'id_voltage_eff', 'id_voltage_meas', ...
        'terminal_voltage', 'id_voltage_cmd', 'Ud', 'ud'});
    if isnan(current) || isnan(voltage)
        rejections.missing_current_or_voltage = rejections.missing_current_or_voltage + 1;
        continue;
    end
    if ~isfinite(current) || ~isfinite(voltage)
        rejections.nonfinite = rejections.nonfinite + 1;
        continue;
    end
    if abs(current) < config.MinAbsCurrentA
        rejections.low_current = rejections.low_current + 1;
        continue;
    end

    speed = optionalNumber(data, row, {'speed', 'FluxWm'});
    if isfinite(speed) && abs(speed) > config.MaxAbsSpeedRpm
        rejections.running = rejections.running + 1;
        continue;
    end

    vbus = optionalNumber(data, row, {'vbus', 'Vbus', 'dc_bus_v'});
    if isfinite(vbus) && (vbus < config.MinVbusV || vbus > config.MaxVbusV)
        rejections.vbus_out_of_range = rejections.vbus_out_of_range + 1;
        continue;
    end

    key = recordLevel(data, row);
    role = recordRole(data, row);
    temperature = optionalNumber(data, row, {'temperature_c', 'motor_temperature_c', ...
        'winding_temperature_c', 'board_temperature_c'});
    timeS = optionalNumber(data, row, {'time_s', 'time', 'timestamp_s'});
    groups = appendGroupSample(groups, key, current, voltage, temperature, timeS, role);
end
end

function groups = appendGroupSample(groups, key, current, voltage, temperature, timeS, role)
groupIndex = find(arrayfun(@(group) group.key == key, groups), 1);
if isempty(groupIndex)
    groupIndex = numel(groups) + 1;
    groups(groupIndex).key = key;
    groups(groupIndex).current = [];
    groups(groupIndex).voltage = [];
    groups(groupIndex).temperature = [];
    groups(groupIndex).time = [];
    groups(groupIndex).role = strings(0, 1);
end

groups(groupIndex).current(end + 1, 1) = current;
groups(groupIndex).voltage(end + 1, 1) = voltage;
groups(groupIndex).temperature(end + 1, 1) = temperature;
groups(groupIndex).time(end + 1, 1) = timeS;
groups(groupIndex).role(end + 1, 1) = role;
end

function [fitPoints, validationPoints, sampleCount, validationSampleCount, rejections] = ...
    reduceGroups(groups, config, rejections)
fitPoints = zeros(0, 3);
validationPoints = zeros(0, 3);
sampleCount = 0;
validationSampleCount = 0;

for groupIndex = 1:numel(groups)
    group = groups(groupIndex);
    keep = settledMask(group.time, config, rejections);
    rejections = countSettlingRejections(group.time, keep, config, rejections);

    current = group.current(keep);
    voltage = group.voltage(keep);
    temperature = group.temperature(keep);
    role = group.role(keep);
    if numel(current) < config.MinSamplesPerLevel
        rejections.too_few_samples = rejections.too_few_samples + numel(current);
        continue;
    end

    meanCurrent = trimmedMean(current, config.TrimFraction);
    meanVoltage = trimmedMean(voltage, config.TrimFraction);
    meanTemperature = meanFiniteOrDefault(temperature, NaN);
    if abs(meanCurrent) < config.MinAbsCurrentA
        continue;
    end

    if any(role == "validation")
        validationPoints(end + 1, :) = [meanCurrent, meanVoltage, meanTemperature]; %#ok<AGROW>
        validationSampleCount = validationSampleCount + numel(current);
    else
        fitPoints(end + 1, :) = [meanCurrent, meanVoltage, meanTemperature]; %#ok<AGROW>
        sampleCount = sampleCount + numel(current);
    end
end

fitPoints = sortrows(fitPoints, 1);
validationPoints = sortrows(validationPoints, 1);
end

function keep = settledMask(timeS, config, rejections) %#ok<INUSD>
keep = true(size(timeS));
if config.LevelSettleTimeS <= 0
    return;
end

finiteTime = isfinite(timeS);
if ~any(finiteTime)
    return;
end

startTime = min(timeS(finiteTime));
keep = finiteTime & (timeS - startTime >= config.LevelSettleTimeS - 1e-12);
end

function rejections = countSettlingRejections(timeS, keep, config, rejections)
if config.LevelSettleTimeS <= 0 || all(~isfinite(timeS))
    return;
end

rejections.missing_time = rejections.missing_time + sum(~isfinite(timeS));
rejections.settling = rejections.settling + sum(isfinite(timeS) & ~keep);
end

function [rsOhm, offsetV, signVoltageV] = fitVoltageModel(points, config)
current = points(:, 1);
voltage = points(:, 2);

if strcmpi(string(config.VoltageModel), "linear_offset")
    x = [current, ones(size(current))];
    params = x \ voltage;
    rsOhm = params(1);
    offsetV = params(2);
    signVoltageV = 0;
    return;
end

if strcmpi(string(config.VoltageModel), "deadtime")
    x = [current, ones(size(current)), sign(current)];
    params = x \ voltage;
    rsOhm = params(1);
    offsetV = params(2);
    signVoltageV = params(3);
    return;
end

error('estimatePmsmRs:unsupportedVoltageModel', 'Unsupported Rs voltage model.');
end

function voltage = predictVoltage(current, rsOhm, offsetV, signVoltageV, config)
voltage = rsOhm .* current + offsetV;
if strcmpi(string(config.VoltageModel), "deadtime")
    voltage = voltage + signVoltageV .* sign(current);
end
end

function rSquared = computeRSquared(voltage, residual)
total = sum((voltage - mean(voltage)).^2);
if total <= 1e-12
    rSquared = 1;
else
    rSquared = 1 - sum(residual.^2) / total;
end
end

function asymmetry = computePositiveNegativeAsymmetry(points, rsOhm)
positive = points(points(:, 1) > 0, :);
negative = points(points(:, 1) < 0, :);
if size(positive, 1) < 2 || size(negative, 1) < 2 || abs(rsOhm) < 1e-12
    asymmetry = Inf;
    return;
end

positiveRs = linearSlope(positive);
negativeRs = linearSlope(negative);
asymmetry = abs(positiveRs - negativeRs) / abs(rsOhm);
end

function slope = linearSlope(points)
x = points(:, 1);
y = points(:, 2);
xMean = mean(x);
yMean = mean(y);
den = sum((x - xMean).^2);
if den <= 1e-12
    error('estimatePmsmRs:poorExcitation', 'Current levels do not excite enough range.');
end
slope = sum((x - xMean) .* (y - yMean)) / den;
end

function rsAtReferenceOhm = temperatureCorrectRs(rsOhm, temperatureC, config)
scale = 1 + config.CopperTempCoeffPerC * (temperatureC - config.ReferenceTemperatureC);
if scale <= 0
    error('estimatePmsmRs:temperatureCorrection', 'Invalid temperature correction scale.');
end
rsAtReferenceOhm = rsOhm / scale;
end

function validationRmseV = computeValidationRmse(validationPoints, rsOhm, offsetV, signVoltageV, config)
if isempty(validationPoints)
    validationRmseV = NaN;
    return;
end

prediction = predictVoltage(validationPoints(:, 1), rsOhm, offsetV, signVoltageV, config);
residual = validationPoints(:, 2) - prediction;
validationRmseV = sqrt(mean(residual.^2));
end

function validateFit(rsOhm, rSquared, rmseV, asymmetry, config)
if rsOhm < config.MinRsOhm || rsOhm > config.MaxRsOhm
    error('estimatePmsmRs:range', 'Rs estimate is outside the configured valid range.');
end
if rSquared < config.MinRSquared
    error('estimatePmsmRs:rSquared', 'Rs fit R-squared is below the configured threshold.');
end
if rmseV > config.MaxRmseV
    error('estimatePmsmRs:fitResidual', 'Rs fit residual is above the configured threshold.');
end
if asymmetry > config.MaxPositiveNegativeAsymmetry
    error('estimatePmsmRs:polarityAsymmetry', ...
        'Positive and negative current levels produce inconsistent Rs.');
end
end

function value = optionalNumber(data, row, names)
value = NaN;
for index = 1:numel(names)
    name = names{index};
    if ismember(name, data.Properties.VariableNames)
        raw = data.(name)(row);
        value = convertToDouble(raw);
        return;
    end
end
end

function value = optionalBool(data, row, names)
value = NaN;
for index = 1:numel(names)
    name = names{index};
    if ismember(name, data.Properties.VariableNames)
        raw = data.(name)(row);
        numeric = convertToDouble(raw);
        if isfinite(numeric)
            value = numeric ~= 0;
        else
            text = lower(strtrim(string(raw)));
            if ismember(text, ["true", "yes", "y", "valid"])
                value = true;
            elseif ismember(text, ["false", "no", "n", "invalid"])
                value = false;
            end
        end
        return;
    end
end
end

function value = convertToDouble(raw)
if iscell(raw)
    raw = raw{1};
end
if isstring(raw) || ischar(raw)
    value = str2double(raw);
else
    value = double(raw);
end
end

function role = recordRole(data, row)
role = "fit";
names = {'id_role', 'id_use', 'role', 'rs_role'};
for index = 1:numel(names)
    name = names{index};
    if ismember(name, data.Properties.VariableNames)
        text = lower(strtrim(string(data.(name)(row))));
        if ismember(text, ["validation", "validate", "holdout", "check"])
            role = "validation";
        end
        return;
    end
end
end

function key = recordLevel(data, row)
for name = ["id_level", "ID_Level"]
    if ismember(char(name), data.Properties.VariableNames)
        key = string(data.(char(name))(row));
        return;
    end
end

currentRef = optionalNumber(data, row, {'id_current_ref', 'Id_ref', 'id_ref', 'current_ref'});
if isfinite(currentRef)
    key = string(round(currentRef, 6));
else
    key = string(row);
end
end

function value = trimmedMean(values, trimFraction)
values = sort(values(:));
trimCount = floor(numel(values) * min(max(trimFraction, 0), 0.45));
if trimCount > 0 && numel(values) > trimCount * 2
    values = values((trimCount + 1):(end - trimCount));
end
value = mean(values);
end

function value = meanFiniteOrDefault(values, defaultValue)
values = values(isfinite(values));
if isempty(values)
    value = defaultValue;
else
    value = mean(values);
end
end
