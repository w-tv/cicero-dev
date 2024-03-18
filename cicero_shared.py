from databricks import sql
import streamlit as st
from typing import Any

@st.cache_data()
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[str]:
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      return cursor.execute(query, sql_params_dict).fetchall()
