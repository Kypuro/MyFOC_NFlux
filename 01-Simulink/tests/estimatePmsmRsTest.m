classdef estimatePmsmRsTest < matlab.unittest.TestCase
    %estimatePmsmRsTest Unit tests for MATLAB-side PMSM Rs identification.

    methods (TestClassSetup)
        function addSourceToPath(testCase)
            testFolder = fileparts(mfilename('fullpath'));
            sourceFolder = fullfile(fileparts(testFolder), 'ParameterIdentification');
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(sourceFolder));
        end
    end

    methods (Test)
        function estimatesRsWithDeadtimeTerm(testCase)
            data = testCase.makeRecords([-0.7, -0.45, -0.25, 0.25, 0.45, 0.7]);
            data.id_voltage_eff = 6.97 .* data.id_current_meas + 0.32 + ...
                0.18 .* sign(data.id_current_meas);

            result = estimatePmsmRs(data);

            testCase.verifyEqual(result.RsOhm, 6.97, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.VoltageOffsetV, 0.32, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.SignVoltageV, 0.18, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.ValidLevelCount, 6);
        end

        function estimatesRsFromCsvFile(testCase)
            data = testCase.makeRecords([-0.6, -0.4, 0.4, 0.6]);
            tempFile = [tempname, '.csv'];
            testCase.addTeardown(@() delete(tempFile));
            writetable(data, tempFile);

            result = estimatePmsmRs(tempFile);

            testCase.verifyEqual(result.RsOhm, 6.97, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.ValidLevelCount, 4);
        end

        function filtersSettlingInvalidAndSaturatedSamples(testCase)
            data = testCase.makeRecordsWithTransientAndBadSamples();
            config = struct('LevelSettleTimeS', 0.02);

            result = estimatePmsmRs(data, config);

            testCase.verifyEqual(result.RsOhm, 6.97, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.SampleCount, 16);
            testCase.verifyEqual(result.RejectionCounts.settling, 16);
            testCase.verifyEqual(result.RejectionCounts.id_invalid, 1);
            testCase.verifyEqual(result.RejectionCounts.pwm_saturated, 8);
        end

        function usesHoldoutValidationOnlyForValidation(testCase)
            fitData = testCase.makeRecords([-0.6, -0.4, 0.4, 0.6]);
            validationData = testCase.makeRecords(0.5);
            validationData.id_level(:) = 200;
            validationData.id_role(:) = "validation";
            data = [fitData; validationData];

            result = estimatePmsmRs(data);

            testCase.verifyEqual(result.RsOhm, 6.97, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.ValidLevelCount, 4);
            testCase.verifyEqual(result.ValidationLevelCount, 1);
            testCase.verifyLessThan(result.ValidationRmseV, 1e-3);
        end

        function rejectsBadHoldoutValidation(testCase)
            fitData = testCase.makeRecords([-0.6, -0.4, 0.4, 0.6]);
            validationData = testCase.makeRecords(0.5);
            validationData.id_level(:) = 200;
            validationData.id_role(:) = "validation";
            validationData.id_voltage_eff = validationData.id_voltage_eff + 0.4;
            data = [fitData; validationData];
            config = struct('MaxValidationRmseV', 0.05);

            testCase.verifyError(@() estimatePmsmRs(data, config), ...
                'estimatePmsmRs:validationResidual');
        end
    end

    methods
        function data = makeRecords(~, levels)
            repeats = 8;
            rowCount = numel(levels) * repeats;
            idLevel = zeros(rowCount, 1);
            current = zeros(rowCount, 1);
            voltage = zeros(rowCount, 1);
            speed = 0.2 * ones(rowCount, 1);
            temperature = 25.0 * ones(rowCount, 1);
            role = repmat("fit", rowCount, 1);
            row = 1;

            for levelIndex = 1:numel(levels)
                levelCurrent = levels(levelIndex);
                for sampleIndex = 1:repeats
                    ripple = (sampleIndex - repeats / 2) * 0.0005;
                    measuredCurrent = levelCurrent + ripple;
                    idLevel(row) = levelIndex - 1;
                    current(row) = measuredCurrent;
                    voltage(row) = 6.97 * measuredCurrent + 0.32;
                    row = row + 1;
                end
            end

            data = table(idLevel, current, voltage, speed, temperature, role, ...
                'VariableNames', {'id_level', 'id_current_meas', 'id_voltage_eff', ...
                'speed', 'temperature_c', 'id_role'});
        end

        function data = makeRecordsWithTransientAndBadSamples(testCase)
            data = testCase.makeTransientRecords([-0.6, -0.4, 0.4, 0.6]);
            invalidSample = table(99, 0.8, 80.0, 0.2, 1.0, 0.0, false, "fit", ...
                'VariableNames', {'id_level', 'id_current_meas', 'id_voltage_eff', ...
                'speed', 'time_s', 'id_valid', 'pwm_saturated', 'id_role'});
            saturatedSamples = testCase.makeSaturatedRecords();
            data = [data; invalidSample; saturatedSamples];
        end

        function data = makeTransientRecords(~, levels)
            repeats = 8;
            rowCount = numel(levels) * repeats;
            idLevel = zeros(rowCount, 1);
            current = zeros(rowCount, 1);
            voltage = zeros(rowCount, 1);
            speed = 0.2 * ones(rowCount, 1);
            time = zeros(rowCount, 1);
            valid = ones(rowCount, 1);
            saturated = false(rowCount, 1);
            role = repmat("fit", rowCount, 1);
            row = 1;

            for levelIndex = 1:numel(levels)
                levelCurrent = levels(levelIndex);
                for sampleIndex = 1:repeats
                    measuredCurrent = levelCurrent + sampleIndex * 0.0002;
                    transientVoltage = 0.8 * double(sampleIndex <= 4);
                    idLevel(row) = levelIndex - 1;
                    current(row) = measuredCurrent;
                    voltage(row) = 6.97 * measuredCurrent + 0.32 + transientVoltage;
                    time(row) = (levelIndex - 1) * 0.1 + (sampleIndex - 1) * 0.005;
                    row = row + 1;
                end
            end

            data = table(idLevel, current, voltage, speed, time, valid, saturated, role, ...
                'VariableNames', {'id_level', 'id_current_meas', 'id_voltage_eff', ...
                'speed', 'time_s', 'id_valid', 'pwm_saturated', 'id_role'});
        end

        function data = makeSaturatedRecords(~)
            rowCount = 8;
            data = table(77 * ones(rowCount, 1), 0.9 * ones(rowCount, 1), ...
                40.0 * ones(rowCount, 1), 0.1 * ones(rowCount, 1), ...
                (1:rowCount)' * 0.001, ones(rowCount, 1), true(rowCount, 1), ...
                repmat("fit", rowCount, 1), ...
                'VariableNames', {'id_level', 'id_current_meas', 'id_voltage_eff', ...
                'speed', 'time_s', 'id_valid', 'pwm_saturated', 'id_role'});
        end
    end
end
