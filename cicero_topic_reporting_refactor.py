#!/usr/bin/env -S streamlit run
"""This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords (internally called "hooks").

List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
  TV Funds: SUM of TV Funds
  FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
  ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
  Sent: SUM of Sent
  Result_Count: Count Distinct of Result Name

  (Since FPM is Funds per mille, I think the symbol should be $‰, but Alex nixed this idea.)
"""
import streamlit as st
from typing import Any, Sequence
from cicero_shared import sql_call
from collections import defaultdict

import pandas as pd
import altair as alt


# two ways we can do this:
# 1. make the external name the key, and store the associated internal names in a list as the value
# 2. make each internal name a key, and have the external name be the value (CURRENT BEHAVIOR)

# method 1
# this, is not working as intended. not sure why. or maybe it is working as intended, and i just don't like the final result.
ext_name_to_int_names_list = sql_call("select account_name, rollup_name from cicero.ref_tables.ref_account_rollup")
ext_name_to_int_names_dict = defaultdict(list)
for row in ext_name_to_int_names_list:
    ext_name_to_int_names_dict[row['rollup_name']].append(row['account_name'])
st.write(list(ext_name_to_int_names_dict)[0:5])

# method 2
int_name_to_ext_name_list = sql_call("select account_name, rollup_name from cicero.ref_tables.ref_account_rollup")
int_name_to_ext_name_dict = {}
for row in int_name_to_ext_name_list:
  int_name_to_ext_name_dict[row['account_name']] = row['rollup_name']
st.write(list(int_name_to_ext_name_list)[0:5])


topics = sql_call('select * from hook_reporting.default.gold_topic_data limit 5')

st.write(topics[0])
