# coding=utf-8
from __future__ import division, print_function

import logging
import os

from tilezen.web import app

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
