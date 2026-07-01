"""Test selenium check logic (not actual browser launch)."""
import os, subprocess, re

class TestSeleniumCheck:
    def test_chrome_binary_exists(self):
        assert os.path.exists(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    def test_chrome_version_readable(self):
        r = subprocess.run(
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
            capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert re.search(r"\d+\.\d+\.\d+\.\d+", r.stdout)

    def test_chromedriver_exists(self):
        import glob
        paths = glob.glob(os.path.expanduser("~/.wdm/**/chromedriver"), recursive=True)
        assert len(paths) > 0, "No chromedriver found in ~/.wdm/"
