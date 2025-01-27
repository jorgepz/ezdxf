
import sys
from os.path import dirname
sys.path.append(dirname('../src/'))

from random import random
from ezdxf.addons import r12writer

MAX_X_COORD = 1000
MAX_Y_COORD = 1000

with r12writer("many_circles.dxf") as doc:
    for _ in range(100000):
        doc.add_circle((MAX_X_COORD*random(), MAX_Y_COORD*random()), radius=2)

