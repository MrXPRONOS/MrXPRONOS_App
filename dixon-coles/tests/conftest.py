import pytest
from dcscore.store import Store
from dcscore.demo import load_demo

@pytest.fixture
def teststore(tmp_path):
    return Store(str(tmp_path / 'test.db'))

@pytest.fixture
def demo_store(teststore):
    load_demo(teststore)
    return teststore
