#!/usr/bin/env -S streamlit run

import streamlit as st
from cicero_shared import sql_call

def main() -> None:
  method = st.radio("Search method", ["Substring (that's the only one right now, sorry)"])
  # TODO: add the case-insensitive version, ilike, as an option.
  # Although this label says substring, it's technically a type of regex if you know how to use it; see https://docs.databricks.com/en/sql/language-manual/functions/like.html. This also lets the user use stuff like \n and \Z if they want.
  # COULD: use the escape argument, in conjunction with a custom replacement logic I would have to write here, to allow the user to input literal percent signs and underscores. But, I mean, who cares? It's about as likely that someone will use it as a feature than as an antifeature that would break something, and I know how rare that is...
  # I also considered exact full-text match but then we'd have to parse the "responsegiven".
  # Which we could do (it's just json), but we'd have to do it on our end. Which could perhaps consume a lot of memory, 1000s of strings; but I haven't measured its impact. Preliminary testing, by searching for substring % (which, being a regex secretly, only filters out some nulls probably), suggests we would only be spending about 20MiB on this, out of our total 1GiB budget. This matches my "napkin math" on it. And that number is low enough that we can ignore it for now, but it might become inconvenient later if/when the project scales up... (could also always limit the date range, or do the operation in chunks, or things like that)
  # We will also probably have to do the text similarity methods (eg Levenshtein, ratcliff-obershelp, maybe others, Jaro-Winkler, various ml things) after unpacking the responses given (and pick a similarity threshold for them? Or perhaps just pick a default and let the user pick...)
  # TODO: actually, databricks SQL already has levenshtein built in! https://docs.databricks.com/en/sql/language-manual/functions/levenshtein.html . We just have to adapt the responsegiven column to use https://docs.databricks.com/en/sql/language-manual/data-types/array-type.html of string, and then we can write a query over it using https://docs.databricks.com/en/sql/language-manual/functions/explode.html (see also this random post for syntax example if need be: https://community.databricks.com/t5/data-engineering/query-array-in-sql/m-p/14571#M9043 ). Maybe take the len of the query string as well, for normalization purposes...
  st.write(method)
  query = st.text_input("Search for responses containing this text (hit enter to send)")
  st.write(query)
  if query:
    st.write(
      sql_call(
        "SELECT * from cicero.default.activity_log WHERE responsegiven LIKE CONCAT('%', %(query)s, '%')",
        {'query': query}
      )
    )
if __name__ == "__main__": main()
