from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
import streamlit as st
import psutil, os
print(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.
Time to display (just importing): {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.""")
st.write(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB. Time to display (importing and running page): {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.""") # Here, you can also have the time to display after the import. Just don't get them confused!
