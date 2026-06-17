function [Rs_hat, Rs_20C, offset_v, sign_v, valid, status, fit_rmse, ...
    val_rmse, level_count, sample_count, reject_count] = rsStandstillIdStep( ...
    enable, reset, finish, sample_valid, id_level, id_current, id_voltage, ...
    speed, temperature_c, pwm_saturated, id_role, RsIdBatch_Init, ...
    RsIdBatch_MinCurrent, RsIdBatch_MaxSpeed, RsIdBatch_MinSamples, ...
    RsIdBatch_MinLevels, RsIdBatch_SettleTicks, RsIdBatch_Min, ...
    RsIdBatch_Max, RsIdBatch_MaxRmse, RsIdBatch_MaxValRmse, ...
    RsIdBatch_RefTemp, RsIdBatch_CuAlpha)
%rsStandstillIdStep Streaming standstill Rs identifier for Simulink use.
%#codegen

MAX_LEVELS = 8;

persistent sum_i sum_v sum_t count role last_level settle_count
persistent rs_hold rs20_hold offset_hold sign_hold valid_hold status_hold
persistent fit_rmse_hold val_rmse_hold level_count_hold sample_count_hold reject_count_hold

if isempty(rs_hold)
    [sum_i, sum_v, sum_t, count, role] = resetStorage(MAX_LEVELS);
    last_level = int32(-999);
    settle_count = int32(0);
    rs_hold = single(RsIdBatch_Init);
    rs20_hold = single(RsIdBatch_Init);
    offset_hold = single(0);
    sign_hold = single(0);
    valid_hold = false;
    status_hold = int32(0);
    fit_rmse_hold = single(NaN);
    val_rmse_hold = single(NaN);
    level_count_hold = int32(0);
    sample_count_hold = int32(0);
    reject_count_hold = int32(0);
end

if reset || ~enable
    [sum_i, sum_v, sum_t, count, role] = resetStorage(MAX_LEVELS);
    last_level = int32(-999);
    settle_count = int32(0);
    rs_hold = single(RsIdBatch_Init);
    rs20_hold = single(RsIdBatch_Init);
    offset_hold = single(0);
    sign_hold = single(0);
    valid_hold = false;
    status_hold = int32(0);
    fit_rmse_hold = single(NaN);
    val_rmse_hold = single(NaN);
    level_count_hold = int32(0);
    sample_count_hold = int32(0);
    reject_count_hold = int32(0);
end

if enable && ~reset
    if finish
        [rs_hold, rs20_hold, offset_hold, sign_hold, valid_hold, status_hold, ...
            fit_rmse_hold, val_rmse_hold, level_count_hold, sample_count_hold] = ...
            computeResult(sum_i, sum_v, sum_t, count, role, RsIdBatch_Init, ...
            RsIdBatch_MinSamples, RsIdBatch_MinLevels, RsIdBatch_Min, ...
            RsIdBatch_Max, RsIdBatch_MaxRmse, RsIdBatch_MaxValRmse, ...
            RsIdBatch_RefTemp, RsIdBatch_CuAlpha);
    elseif sample_valid && ~pwm_saturated && abs(speed) <= RsIdBatch_MaxSpeed && ...
            abs(id_current) >= RsIdBatch_MinCurrent
        level = clampLevel(id_level, MAX_LEVELS);
        if level ~= last_level
            last_level = level;
            settle_count = int32(0);
        end

        if settle_count < RsIdBatch_SettleTicks
            settle_count = settle_count + int32(1);
            reject_count_hold = reject_count_hold + int32(1);
        else
            idx = double(level);
            sum_i(idx) = sum_i(idx) + single(id_current);
            sum_v(idx) = sum_v(idx) + single(id_voltage);
            sum_t(idx) = sum_t(idx) + single(temperature_c);
            count(idx) = count(idx) + int32(1);
            if id_role ~= int32(0)
                role(idx) = int32(1);
            end
        end
    else
        reject_count_hold = reject_count_hold + int32(1);
    end
end

Rs_hat = rs_hold;
Rs_20C = rs20_hold;
offset_v = offset_hold;
sign_v = sign_hold;
valid = valid_hold;
status = status_hold;
fit_rmse = fit_rmse_hold;
val_rmse = val_rmse_hold;
level_count = level_count_hold;
sample_count = sample_count_hold;
reject_count = reject_count_hold;
end

function [sum_i, sum_v, sum_t, count, role] = resetStorage(maxLevels)
sum_i = zeros(maxLevels, 1, 'single');
sum_v = zeros(maxLevels, 1, 'single');
sum_t = zeros(maxLevels, 1, 'single');
count = zeros(maxLevels, 1, 'int32');
role = zeros(maxLevels, 1, 'int32');
end

function level = clampLevel(idLevel, maxLevels)
level = idLevel + int32(1);
if level < int32(1)
    level = int32(1);
elseif level > int32(maxLevels)
    level = int32(maxLevels);
end
end

function [rs, rs20, offset, signVoltage, valid, status, fitRmse, valRmse, ...
    levelCount, sampleCount] = computeResult(sumI, sumV, sumT, count, role, ...
    initRs, minSamples, minLevels, minRs, maxRs, maxRmse, maxValRmse, ...
    refTemp, cuAlpha)

normal = zeros(3, 3, 'single');
rhs = zeros(3, 1, 'single');
fitVoltage = zeros(8, 1, 'single');
fitCurrent = zeros(8, 1, 'single');
fitTemp = zeros(8, 1, 'single');
fitN = int32(0);
valResidualSum = single(0);
valN = int32(0);
sampleCount = int32(0);

for idx = 1:8
    if count(idx) >= minSamples
        iMean = sumI(idx) / single(count(idx));
        vMean = sumV(idx) / single(count(idx));
        tMean = sumT(idx) / single(count(idx));
        if role(idx) == int32(0)
            row = [iMean; single(1); localSign(iMean)];
            normal = normal + row * row';
            rhs = rhs + row * vMean;
            fitN = fitN + int32(1);
            fitCurrent(double(fitN)) = iMean;
            fitVoltage(double(fitN)) = vMean;
            fitTemp(double(fitN)) = tMean;
            sampleCount = sampleCount + count(idx);
        end
    end
end

levelCount = fitN;
valRmse = single(NaN);
fitRmse = single(NaN);
rs = single(initRs);
rs20 = single(initRs);
offset = single(0);
signVoltage = single(0);
valid = false;

if fitN < minLevels
    status = int32(-1);
    return;
end

[params, ok] = solve3x3(normal, rhs);
if ~ok
    status = int32(-2);
    return;
end

rs = params(1);
offset = params(2);
signVoltage = params(3);

residualSum = single(0);
for idx = 1:double(fitN)
    pred = rs * fitCurrent(idx) + offset + signVoltage * localSign(fitCurrent(idx));
    residual = fitVoltage(idx) - pred;
    residualSum = residualSum + residual * residual;
end
fitRmse = sqrt(residualSum / single(fitN));

tempMean = meanUsedTemperature(fitTemp, fitN, refTemp);
scale = single(1) + cuAlpha * (tempMean - refTemp);
if scale > single(0)
    rs20 = rs / scale;
else
    rs20 = rs;
end

for idx = 1:8
    if count(idx) >= minSamples && role(idx) ~= int32(0)
        iMean = sumI(idx) / single(count(idx));
        vMean = sumV(idx) / single(count(idx));
        pred = rs * iMean + offset + signVoltage * localSign(iMean);
        residual = vMean - pred;
        valResidualSum = valResidualSum + residual * residual;
        valN = valN + int32(1);
    end
end
if valN > int32(0)
    valRmse = sqrt(valResidualSum / single(valN));
end

if rs < minRs || rs > maxRs
    status = int32(-3);
elseif fitRmse > maxRmse
    status = int32(-4);
elseif isfinite(valRmse) && valRmse > maxValRmse
    status = int32(-5);
else
    valid = true;
    status = int32(1);
end
end

function s = localSign(value)
if value >= single(0)
    s = single(1);
else
    s = single(-1);
end
end

function tempMean = meanUsedTemperature(fitTemp, fitN, refTemp)
tempSum = single(0);
tempN = int32(0);
for idx = 1:double(fitN)
    if isfinite(fitTemp(idx))
        tempSum = tempSum + fitTemp(idx);
        tempN = tempN + int32(1);
    end
end
if tempN > int32(0)
    tempMean = tempSum / single(tempN);
else
    tempMean = refTemp;
end
end

function [x, ok] = solve3x3(a, b)
aug = [a, b];
ok = true;
for pivot = 1:3
    pivotRow = pivot;
    pivotAbs = abs(aug(pivot, pivot));
    for row = pivot + 1:3
        if abs(aug(row, pivot)) > pivotAbs
            pivotRow = row;
            pivotAbs = abs(aug(row, pivot));
        end
    end
    if pivotAbs < single(1e-7)
        ok = false;
        x = zeros(3, 1, 'single');
        return;
    end
    if pivotRow ~= pivot
        tmp = aug(pivot, :);
        aug(pivot, :) = aug(pivotRow, :);
        aug(pivotRow, :) = tmp;
    end
    aug(pivot, :) = aug(pivot, :) / aug(pivot, pivot);
    for row = 1:3
        if row ~= pivot
            aug(row, :) = aug(row, :) - aug(row, pivot) * aug(pivot, :);
        end
    end
end
x = aug(:, 4);
end
