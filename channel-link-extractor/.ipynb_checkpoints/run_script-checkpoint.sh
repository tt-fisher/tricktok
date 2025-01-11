#!/bin/bash

# Set the path for conda
export PATH="/opt/conda/condabin:$PATH"

# Initialize conda
source /opt/conda/etc/profile.d/conda.sh
conda activate sharedPython  #

# 
python /home/fosh/tricktok/channel-link-extractor/run.py  # 
