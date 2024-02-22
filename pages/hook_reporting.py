from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
from databricks import sql
import os, psutil, platform

st.set_page_config(
  layout="wide",
  page_title="Hook Reporting", #this is of questionable usefulness, as it just changes the browser tab display.
  page_icon="🪝",
)
st.write("TODO: put hook reporting here.")

def get_base_url() -> str:
  #This part is from BramVanroy https://github.com/streamlit/streamlit/issues/798#issuecomment-1647759949
  import urllib.parse
  # "WARNING: I found that in multi-page apps, this will always only return the base url and not the sub-page URL with the page appended to the end."
  session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
  return urllib.parse.urlunparse([session.client.request.protocol, session.client.request.host, "", "", "", ""]) # for example, in testing, this value is probably: http://localhost:8501

#@st.cache_data()
def sql_call(query: str) -> list[str]: #possibly add a params dict param?
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      return cursor.execute(query).fetchall()

#To minimize RAM usage on the front end, most of the computation is done in the sql query, on the backend.
# (maybe do this later:) To minimize latency, all of the stats are queried at once, where possible

"""List of graphs, top to bottom:

    TV Funds - SUM of TV Funds
    FPM - SUM([TV_FUNDS]) / SUM([SENT]) * 1000
    ROAS - SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT])
    Sent - SUM of Sent
    Result Count - Count Distinct of Result Name"""

#x = overall_sum_of_tv_funds = sql_call("SELECT SUM(TV_FUNDS) FROM main.hook_reporting.hook_data_prod")[0][0] #not actually used anywhere
funds, fpm, roas, sent, result_count = x = sql_call("""WITH stats(funds, sent, spend, result_count) AS (SELECT SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT RESULT_NAME) FROM main.hook_reporting.hook_data_prod)
SELECT funds, funds / sent * 1000, funds/spend, sent, result_count from stats""")[0] #not actually used anywhere, but sort of related to what's on the graph

funds, fpm, roas, sent, result_count = x = sql_call("""WITH stats(funds, sent, spend, result_count) AS (SELECT SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT RESULT_NAME) FROM main.hook_reporting.hook_data_prod WHERE PROJECT_TYPE="Text Message: P2P" and GOAL="Fundraising" and SEND_DATE="2024-01-01")
SELECT funds, funds / sent * 1000, funds/spend, sent, result_count from stats""")[0] #not actually used anywhere, but sort of related to what's on the graph # TODO: need to dedup these because of the hook duplication structure.

st.write(x)

st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.<br>
Python version: {platform.python_version()}<br>
Base url: {get_base_url()}""", unsafe_allow_html=True)
