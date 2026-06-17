classdef rsStandstillIdStepTest < matlab.unittest.TestCase
    %rsStandstillIdStepTest Tests streaming Simulink Rs ID step function.

    methods (TestClassSetup)
        function addSourceToPath(testCase)
            testFolder = fileparts(mfilename('fullpath'));
            sourceFolder = fullfile(fileparts(testFolder), 'ParameterIdentification');
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(sourceFolder));
        end
    end

    methods (Test)
        function estimatesRsAfterFinish(testCase)
            testCase.resetEstimator();
            testCase.feedFitLevels([-0.6, -0.4, 0.4, 0.6], 6.97, 0.32, 0.18);

            result = testCase.finishEstimator();

            testCase.verifyTrue(result.Valid);
            testCase.verifyEqual(result.Status, int32(1));
            testCase.verifyEqual(double(result.RsOhm), 6.97, 'AbsTol', 1e-3);
            testCase.verifyEqual(double(result.OffsetV), 0.32, 'AbsTol', 1e-3);
            testCase.verifyEqual(double(result.SignVoltageV), 0.18, 'AbsTol', 1e-3);
            testCase.verifyEqual(result.LevelCount, int32(4));
        end

        function rejectsBadValidationLevel(testCase)
            testCase.resetEstimator();
            testCase.feedFitLevels([-0.6, -0.4, 0.4, 0.6], 6.97, 0.32, 0.0);
            testCase.feedValidationLevel(0.5, 6.97, 0.32, 0.4);

            result = testCase.finishEstimator();

            testCase.verifyFalse(result.Valid);
            testCase.verifyEqual(result.Status, int32(-5));
            testCase.verifyGreaterThan(result.ValidationRmseV, 0.1);
        end
    end

    methods
        function resetEstimator(testCase)
            testCase.callStep(true, true, false, false, 0, 0, 0, 0, 20, false, 0);
        end

        function feedFitLevels(testCase, levels, rs, offset, signVoltage)
            for levelIndex = 1:numel(levels)
                currentLevel = levels(levelIndex);
                for sampleIndex = 1:10
                    current = currentLevel + sampleIndex * 0.0002;
                    voltage = rs * current + offset + signVoltage * sign(current);
                    testCase.callStep(true, false, false, true, levelIndex - 1, ...
                        current, voltage, 0.1, 25.0, false, 0);
                end
            end
        end

        function feedValidationLevel(testCase, currentLevel, rs, offset, voltageError)
            for sampleIndex = 1:10
                current = currentLevel + sampleIndex * 0.0002;
                voltage = rs * current + offset + voltageError;
                testCase.callStep(true, false, false, true, 7, ...
                    current, voltage, 0.1, 25.0, false, 1);
            end
        end

        function result = finishEstimator(testCase)
            [rsOhm, rs20C, offsetV, signVoltageV, valid, status, fitRmseV, ...
                validationRmseV, levelCount, sampleCount, rejectCount] = ...
                testCase.callStep(true, false, true, false, 0, 0, 0, 0, 25, false, 0);
            result = struct( ...
                'RsOhm', rsOhm, ...
                'Rs20C', rs20C, ...
                'OffsetV', offsetV, ...
                'SignVoltageV', signVoltageV, ...
                'Valid', valid, ...
                'Status', status, ...
                'FitRmseV', fitRmseV, ...
                'ValidationRmseV', validationRmseV, ...
                'LevelCount', levelCount, ...
                'SampleCount', sampleCount, ...
                'RejectCount', rejectCount);
        end

        function varargout = callStep(~, enable, reset, finish, sampleValid, idLevel, ...
                idCurrent, idVoltage, speed, temperatureC, pwmSaturated, idRole)
            [varargout{1:nargout}] = rsStandstillIdStep( ...
                enable, reset, finish, sampleValid, int32(idLevel), ...
                single(idCurrent), single(idVoltage), single(speed), ...
                single(temperatureC), pwmSaturated, int32(idRole), ...
                single(6.97), single(0.05), single(5.0), int32(3), ...
                int32(4), int32(2), single(0.1), single(50.0), ...
                single(0.1), single(0.1), single(20.0), single(0.00393));
        end
    end
end
