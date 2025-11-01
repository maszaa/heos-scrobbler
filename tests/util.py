import os

import pytest

integration_test = pytest.mark.skipif(
    os.getenv("ENABLE_INTEGRATION_TESTS", str(False)).capitalize() != str(True), reason="Integration tests not enabled"
)
