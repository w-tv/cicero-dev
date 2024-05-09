#!/usr/bin/env -S streamlit run
"""It's useless to run this stand-alone. But I guess you can."""

from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row
import streamlit as st
from typing import Any, NoReturn

def exit_error(exit_code: int) -> NoReturn:
  st.write("*Ego vero consisto. Accede, veterane, et, si hoc saltim potes recte facere, incide cervicem.*")
  exit(exit_code)

@st.cache_data()
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """This is a wrapper function for sql_call_cacheless that *is* cached. See that other function for more information about the actual functionality."""
  return sql_call_cacheless(query, sql_params_dict)

def sql_call_cacheless(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """Make a call to the database, returning a list of Rows. The returned values within the Rows are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions"""
  # COULD: (but probably won't) there is a minor problem where we'd like to ensure that a query to a table x only occurs after a call to CREATE TABLE IF NOT EXISTS x (parameters of x). Technically, we could ensure this by creating a new function ensure_table(table_name, table_types) which then returns an TableEnsurance object, which then must be passed in as a parameter to SQL call. However, then we would want to check if it were the correct table (and possibly the right parameter types) which would greatly complicate the function signature of sql_call, because we'd have to pass the table name(s) in too, and then string-replace them into the query(?). So, doesn't seem worth it.
  try:
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query, sql_params_dict).fetchall()
  except Exception as e:
    print(e.args)
    st.write(f"There was a database error, and the application could not continue. Sorry.") #COULD: this usually prints to the second tab, because we load it first, which is not ideal...
    st.code(e.args)
    exit_error(4)

def pod_from_email(email: str) -> str:
  """TODO: (low priority) This could probably be done in sql in the activity log insert, using a common table expression or something."""
  keyword_arguments = locals() # This is a dict of the arguments passed to the function. It must be called at the top of the function, because if it is called later then it will list any other local variables as well.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.user_pods (user_email string, user_pod string)")
  return sql_call("SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike %(email)s", keyword_arguments)[0][0] or "Pod unknown"
