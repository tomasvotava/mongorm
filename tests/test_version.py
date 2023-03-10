from mongorm.version import __version__


def test_version():
    assert len(__version__.split(".")) == 3, "Version number must have three parts"
    assert __version__ > "0.0.0", "Version number must be larger than 0.0.0"
