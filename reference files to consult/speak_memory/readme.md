# Speak Memory

2023-12-12

Speaking of memory, we've been running out of memory in the streamlit community cloud (limit: 1 GiB) due to what seems to be some kind of memory leak (possibly with the use of faiss?). To investigate that, I created streamlit_app_baseline_performance.py, and other variants, to see what baselines we're working from.

One of the curious features of the OOM is that it often happens in the middle of the night, when we don't think anyone's probably using Cicero. My theory about that, after the below investigation, is that it's just using up most of the memory + random fluctuations in memory usage pushing us over the line.

Terminological Note: I will call the Cicero app (the .py file that runs) the "front end" and "client" since it serves data to the "back end" (the model). This is NOT to be confused with the fact that every Cicero web page is also a front-end and client to the cicero app, that is running on some server somewhere; even though that's technically true, it's not relevant here. I will refer to the presentation instances in the browser as "tabs", because that's also what they are.

streamlit run streamlit_app_baseline_performance.py
> Streamlit app memory usage: 123 MiB.
> Time to display: 0.0001217 seconds.

(extra browser windows to the same instance of this empty st app don't seem to add much memory.)

cpython_importing_streamlit_baseline_performance.py:
> Streamlit app memory usage: 85 MiB.
> Time to display: 1.2306231 seconds.

cpython_baseline_performance.py
> Streamlit app memory usage: 14 MiB.
> Time to display: 0.0597102 seconds.

streamlit run streamlit_app.py
> Streamlit app memory usage: 388 MiB.
> Time to display: 156.2798211 seconds.

The app doesn't seem to grow in memory usage if you just leave it running in the background. However, if you use a semantic query, it jumps up to:

> Streamlit app memory usage: 501 MiB.

(using a semantic query a second time won't take up additional memory)

Reseting with the reset button goes down to:

> Streamlit app memory usage: 409 MiB.

If two sessions are both using a semantic query:

> Streamlit app memory usage: 600 MiB.

Interestingly, if those two tabs are closed and a new tab that isn't using any vector embedding is opened, the memory usage is still 600MiB. If the browser is closed and reopened, the memory usage goes down. This may be a limitation because I am testing from the same computer/ip (I tested it with a different concurrent browser, instead of just two and got the same behavior as the current browser — or at least it takes a many minutes, it seems) — so maybe I register as "the same session" and it doesn't garbage-collect the old embeddings until all my connections are closed. OK on 2023-12-13 I tested it with two different computers from two different networks and got the same results: it takes like 10 minutes for the resources to be collected.

Other than that, the memory usage fluctuates up and down by about 20MiB. This is just the garbage collector doing its thing, but might ask a more subtle memory leak. Also, the program slowly consumes in tiny increments more memory as it used, to track past prompts.

## Conclusion

since the production version of Cicero was silently calling embed_into_vector (prod is derived from a time when we were testing out that feature), we were spending 100MiB on that each time someone loaded the page. So, certainly, if 6 people were using the app, it would crash. In the dev version as of 2023-12-12, a vector-embedding is generated only if the user explicitly does a semantic query, so 6 users would have to do that for it to crash.

Even if the memory-leak-type problem was solved (test later? (tested later: mostly solved, in dev), probably more than 6 people will have a session open with a vector embedding in, if this product is successful, so the current behavior is unacceptable anyway.

## Possible solutions

- The dev version also caches the function that does a semantic query, and therefore the vector embeding. If making the user spend 10 seconds per query (a low-frequency operation) is acceptable, we could try not caching it and seeing if the garbage collector just collects it.
- We could also make the vector embedding live in databricks, as we're experimenting with, and perhaps a query to databricks will take only 2 seconds, and also minize the amount of memory used by the client.
- We could investigate if other vector-embedding libraries generate a data structure that takes up a smaller amount of memory, and use that in cicero instead.
- We could also host the streamlit app elsewhere.
- Fiddle about with https://docs.python.org/3/library/gc.html

## Suggested solution

Perhaps "don't cache the vector embedding" is the best choice, if it works. I will try that as soon as we can run a couple tests in the current version. (OK I did those tests.)

It's interesting to consider if we expect any 6 users of Cicero to do a semantic query *at the same time*.
