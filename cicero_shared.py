from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row
import streamlit as st
from typing import Any, cast

@st.cache_data()
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]: #The returned values are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      return cursor.execute(query, sql_params_dict).fetchall() #type: ignore[no-any-return] #I tentatively conclude this is a MYPY-BUG-WORKAROUND, because you can get the rest of databricks-sql-connector to typecheck properly, it seems, except for this... but it might be a databricks-sql-connector-bug-workaround.
