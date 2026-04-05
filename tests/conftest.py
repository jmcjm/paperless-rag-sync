import tempfile
import os

import pytest

from paperless_rag_sync.state import StateDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        state = StateDB(db_path)
        yield state
        state.close()
