import pytest
from openfieldday.sources.base import Source


def test_source_is_abstract():
    with pytest.raises(TypeError):
        Source()  # cannot instantiate abstract base
