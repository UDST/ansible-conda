import json
import unittest

from conda import parse_conda_stdout


class TestParseCondaStdout(unittest.TestCase):
    """
    Tests for `parse_conda_stdout`.
    """
    _VALID_STDOUT = """
        {
          "actions": {}, 
          "success": true
        }
    """

    def test_parses_invalid_stdout(self):
        self.assertIsNone(parse_conda_stdout("fail"))

    def test_parses_valid_stdout(self):
        self.assertEqual(
            json.loads(TestParseCondaStdout._VALID_STDOUT), parse_conda_stdout(TestParseCondaStdout._VALID_STDOUT))

    def test_parses_valid_stdout_with_progress_reports(self):
        stdout = '{"maxval": 17685, "finished": false, "fetch": "translationstr", "progress": 0}\n\x00' \
                 '{"maxval": 17685, "finished": true, "fetch": "translationstr", "progress": 17685}\n\x00%s' \
                 % (TestParseCondaStdout._VALID_STDOUT,)
        self.assertEqual(json.loads(TestParseCondaStdout._VALID_STDOUT), parse_conda_stdout(stdout))


if __name__ == "__main__":
    unittest.main()
