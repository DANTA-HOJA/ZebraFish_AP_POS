import sys
from pathlib import Path

abs_module_path = Path("./../../").resolve()
if (abs_module_path.exists()) and (str(abs_module_path) not in sys.path):
    sys.path.append(str(abs_module_path)) # add path to scan customized module

from modules.dl.tester.fishtester.vitb16fishtester import VitB16FishTester
from modules.shared.utils import get_repo_root

""" Detect Repository """
print(f"Repository: '{get_repo_root()}'")


vit_b_16_fish_tester = VitB16FishTester()
vit_b_16_fish_tester.run()