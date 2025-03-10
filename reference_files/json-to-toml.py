#!/usr/bin/env python3
""" This helper script is from https://gist.github.com/pgilad/e8ffd8ce2bde81a1a375e86df77a34ab
Usage is `json_to_toml.py input.json output.toml`
Don't forget to `pip install toml`.
"""
import json
import sys
import toml

if len(sys.argv) != 3:
  raise Exception('Usage is `json_to_toml.py input.json output.toml`')
json_file = sys.argv[1]
output_file = sys.argv[2]

with open(json_file) as source:
  config = json.loads(source.read())

config = {"google_signin_secrets": config} #this line is new, and domain-specific to us

toml_config = toml.dumps(config)

with open(output_file, 'w') as target:
  target.write(toml_config)
