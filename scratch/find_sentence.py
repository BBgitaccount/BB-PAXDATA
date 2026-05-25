import os
import sys

sys.path.insert(0, os.path.abspath("src"))
import inspect

from bb_paxdata.infrastructure.db.models import Sentence

print("File:", inspect.getsourcefile(Sentence))
print("Line:", inspect.getsourcelines(Sentence)[1])
