#!/usr/bin/env -S streamlit run

import streamlit as st
from cicero_shared import sql_call

r = str(st.radio("Search method", ["Substring", "Case-insensitive substring", "Exact, total match", "Levenshtein"]))[0] #this [0] just saves us verbosity later. The str() call suppresses the obscure possibility that no option is selected, by giving us "None" in that case.
# Although this label says substring, it's technically a type of regex if you know how to use it; see https://docs.databricks.com/en/sql/language-manual/functions/like.html. This also lets the user use stuff like \n and \Z if they want. COULD: use the escape argument, in conjunction with a custom replacement logic I would have to write here, to allow the user to input literal percent signs and underscores. But, I mean, who cares? It's about as likely that someone will use it as a feature than as an antifeature that would break something, and I know how rare that is...
# We could do other local strategies our end, if we like. Which could perhaps consume a lot of memory, 1000s of strings; but I haven't measured its impact. Preliminary testing, by searching for substring % (which, being a regex secretly, only filters out some nulls probably), suggests we would only be spending about 20MiB on this, out of our total 1GiB budget. This matches my "napkin math" on it. And that number is low enough that we can ignore it for now, but it might become inconvenient later if/when the project scales up... (could also always limit the date range, or do the operation in chunks, or things like that)
# TODO: We will also probably have to do other text similarity methods (eg word-presorted-Levenshtein, ratcliff-obershelp, maybe others, Jaro-Winkler, various ml things) after unpacking the responses given (and pick a similarity threshold for them? Or perhaps just pick a default and let the user pick...)
query = st.text_input("Search for responses containing this text (hit enter to send)")
st.write(query)
if query:
  results = sql_call(
    f"""WITH s AS ( SELECT explode(from_json(responsegiven, "array<string>")), *  from cicero.default.activity_log ) -- Note: the explode produces a cartesian product between the responses and the singleton of the row. So, if you have five responses per row, you will get 5 rows in the final results for each row in the activity log, corresponing to (_1, _2, _3, _4, _5)×(row). This also means every result contains a specific result, and a json of all the results. Col is the automatically-assigned name of the column of exploded json array response.
     SELECT * from s WHERE {
      {
        'E': "col == :query",
        'S': "col LIKE CONCAT('%', :query, '%')",
        'C': "col ILIKE CONCAT('%', :query, '%')",
        'L': "levenshtein(col, :query) < len(col) * .69 ORDER BY levenshtein(col, :query) DESC -- the * .69 thing is just an arbitrary heuristic; a little over half of the length of the response. Brief and non-exhaustive empirical investigation yielded this number; it could probably be refined.",
        'N': "true -- N is an extremely obscure edge-case I don't even know how to trigger, but true is a sensible default for it I suppose"
      }[r]
    }""",
    {'query': query}
  )
  st.write(results)
