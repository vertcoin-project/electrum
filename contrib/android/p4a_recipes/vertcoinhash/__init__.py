from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.util import HashPinnedDependency

assert CompiledComponentsPythonRecipe.depends == ['python3']
assert CompiledComponentsPythonRecipe.python_depends == []


class VertcoinhashRecipe(CompiledComponentsPythonRecipe):
    # vertcoinhash's C Verthash for header checks, and (1.1.0 and later) create_datafile, its port of
    # Vertcoin Core's verthash.dat generator. Built from the sdist with setup.py's -fno-strict-aliasing.
    # The sdist is the one vertcoinhash-python's Guix build makes reproducibly, and which its release
    # workflow uploads to PyPI.
    version = "1.1.1"
    sha512sum = "e318093b896877ecf9258ff29495d802f37c073edb9bc51281512d08175a4ca7f7198bfdae91539ad7cc5833ec9113720e2a08954cf273fb3e113cf3a5591471"
    url = "https://files.pythonhosted.org/packages/source/v/vertcoinhash/vertcoinhash-{version}.tar.gz"
    site_packages_name = "verthash"
    call_hostpython_via_targetpython = False
    hostpython_prerequisites = [
        HashPinnedDependency(package="setuptools==80.9.0",
                             hashes=['sha256:062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922']),
    ]


recipe = VertcoinhashRecipe()
