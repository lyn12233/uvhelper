from . import uvstrap
from . import uvconfig

import sys

if __name__ == "__main__":
    if len(sys.argv) == 0:
        exit(-1)
    elif len(sys.argv) == 1:
        uvstrap.strap()
    else:
        opt = sys.argv[1]
        del sys.argv[1]
        match opt:
            case "strap":
                sys.argv[0] = "python -m uvhelper strap"
                uvstrap.strap()
            case "config":
                sys.argv[0] = "python -m uvhelper config"
                # this will be replaced with a proper cli later
                uvconfig.test_config()
            case _:
                raise NotImplementedError(f"opt not available")
