from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row
import streamlit as st
from typing import Any

@st.cache_data()
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """Make a call to the database, returning a list of Rows. The returned values within the Rows are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions"""
  try:
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query, sql_params_dict).fetchall()
  except Exception as e:
    print(e.args)
    st.write(f"There was a database error, and the application could not continue. Sorry.") #COULD: this usually prints to the second tab, because we load it first, which is not ideal...
    st.code(e.args)
    exit(4)
