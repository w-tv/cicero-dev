# Dashboard Specification

## dashboard

Note: at the moment, this component has been reconcieved as a page in cicero.

A fun little dashboard for cool guys

If you are the CLIENT, please add a description of what the project should do ; you can put text in the readme here and screenshots also in this folder.

If you are the DEVELOPER, implement the dashboard in streamlit. (`streamlit run dashboard.py`).

## Client

Here is a [link](https://dbc-ca8d208b-aaa9.cloud.databricks.com/explore/data/main/hook_reporting/hook_data_prod?o=8188181812650195) to the specific table that the data is in. The goal is to replicate a currently existing dashboard that is currently hosted in Tableau Online. There are certain Tableau features that I am not sure are possible to implement in Streamlit, but there are also new features that may be possible to implement in Streamlit that are impossible in Tableau.

List of graphs, top to bottom:
1. TV Funds - SUM of TV Funds
2. FPM - SUM([TV_FUNDS]) / SUM([SENT]) * 1000
3. ROAS - SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT])
4. Sent - SUM of Sent
5. Result Count - Count Distinct of Result Name

REACH GOAL

Fantastical feature that, depending on the filters of the dashboard, generates a prompt in Cicero ready to be submitted.

CLIENT TASKS

- Upload screenshots of dashboard
- Give Developer copy of dashboard that he can interact with (if possible)
- Generate fleshed out list of requirements

## Chronobucketing

Day vs week vs month bucketing is currently 3 different tabs in the old dashboard, but could simply be a control. In fact, it would be better as a control. But if it's computationally less expensive to have it on separate tabs for some reason, that's fine too.

## The Right Black Graph
The right black graph is all_hooks, but controlled by the search filtering as well. It should ideally be combined into the left graph.
