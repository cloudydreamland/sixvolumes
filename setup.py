from pathlib import Path
from setuptools import find_packages, setup

packages = []
package_dir = {}
for root in ["src"] + [f"vendor/{p}/src" for p in ("helan", "worddael", "gewita", "siftan", "tellan", "sothstan")]:
    for name in find_packages(root):
        packages.append(name)
        package_dir[name] = str(Path(root) / name.replace(".", "/"))
setup(packages=packages, package_dir=package_dir,
      package_data={"sixvolumes": ["data/**/*", "data/*"],
                    "sothstan": ["baselines/*.json", "py.typed"],
                    "tellan": ["prices.json", "py.typed"],
                    "helan": ["py.typed"], "worddael": ["py.typed"], "gewita": ["py.typed"]})
