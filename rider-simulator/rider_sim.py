# app.py
import json
from datetime import datetime

import simpy
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import streamlit as st

# ─────────────────────────── Simulation core ──────────────────────────── #
class RiderTrackSimulation:
    def __init__(self, params: dict):
        self.env = simpy.Environment()
        self.p = params

        # Track resources for the three practice zones
        self.zone_a = simpy.Resource(self.env, capacity=params["capZone"])
        self.zone_b = simpy.Resource(self.env, capacity=params["capZone"])
        self.zone_c = simpy.Resource(self.env, capacity=params["capZone"])

        # Stats containers
        self.events, self.queue, self.util = [], [], {"A": [], "B": [], "C": []}

        # Synchronisation events
        self.inst_done = self.env.event()
        self.exp_done = self.env.event()
        if params["nEXP"] == 0:
            self.exp_done.succeed()          # nothing to wait for

        # Completion barrier
        self.done_event = self.env.event()
        self.total_riders = 1 + params["nEXP"] + params["nFOC"]
        self.finished = 0

        # Instructor enters first
        self.env.process(self.rider("INST-1", "INST"))

    # ---------------- helper recorders ---------------- #
    def rec(self, rid, rtype, zone, action):
        self.events.append(dict(
            rider_id=rid,
            rider_type=rtype,
            zone=zone,
            action=action,
            time=self.env.now
        ))

    def monitor_queue(self):
        while True:
            entered = sum(e["zone"] == "Queue" and e["action"] == "enter" for e in self.events)
            exited  = sum(e["zone"] == "Queue" and e["action"] == "exit"  for e in self.events)
            self.queue.append(dict(time=self.env.now, queue_len=entered - exited))
            yield self.env.timeout(0.5)

    def monitor_util(self, tag, res):
        while True:
            self.util[tag].append(dict(
                time=self.env.now,
                utilization=res.count / res.capacity
            ))
            yield self.env.timeout(0.5)

    # ---------------- main rider process ---------------- #
    def rider(self, rid, rtype):
        # Enter queue
        self.rec(rid, rtype, "Queue", "enter")

        # Enter gate (Zone A)
        with self.zone_a.request() as rq:
            yield rq
            self.rec(rid, rtype, "Queue", "exit")
            self.rec(rid, rtype, "Gate", "enter")
            yield self.env.timeout(self.p["tEnter"])
            self.rec(rid, rtype, "Gate", "exit")
            if rtype == "INST":
                self.inst_done.succeed()

        # Zone A
        self.rec(rid, rtype, "ZoneA", "enter")
        yield self.env.timeout(self.p["tA"])
        self.rec(rid, rtype, "ZoneA", "exit")

        # Zone B
        with self.zone_b.request() as rq:
            yield rq
            self.rec(rid, rtype, "ZoneB", "enter")
            yield self.env.timeout(self.p["tB"])
            self.rec(rid, rtype, "ZoneB", "exit")

        # Zone C
        with self.zone_c.request() as rq:
            yield rq
            self.rec(rid, rtype, "ZoneC", "enter")
            yield self.env.timeout(self.p["tC"])
            self.rec(rid, rtype, "ZoneC", "exit")

        # Exit gate
        self.rec(rid, rtype, "Exit", "enter")
        yield self.env.timeout(self.p["tExit"])
        self.rec(rid, rtype, "Exit", "exit")

        # Mark EXP completion
        if rtype == "EXP":
            done_exp = len([
                e for e in self.events
                if e["rider_type"] == "EXP" and e["zone"] == "Exit" and e["action"] == "exit"
            ])
            if done_exp == self.p["nEXP"]:
                self.exp_done.succeed()

        # Final barrier
        self.finished += 1
        if self.finished == self.total_riders and not self.done_event.triggered:
            self.done_event.succeed()

    # ---------------- inject batches ---------------- #
    def inject_exp(self):
        yield self.inst_done
        for i in range(1, self.p["nEXP"] + 1):
            self.env.process(self.rider(f"EXP-{i}", "EXP"))

    def inject_foc(self):
        yield self.exp_done
        for i in range(1, self.p["nFOC"] + 1):
            self.env.process(self.rider(f"FOC-{i}", "FOC"))

    # ---------------- run simulation ---------------- #
    def run(self):
        # Start monitors and injectors
        self.env.process(self.monitor_queue())
        self.env.process(self.monitor_util("A", self.zone_a))
        self.env.process(self.monitor_util("B", self.zone_b))
        self.env.process(self.monitor_util("C", self.zone_c))
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())

        # Run until all riders finish
        self.env.run(until=self.done_event)

        total = max(e["time"] for e in self.events) if self.events else 0
        return dict(events=self.events, queue=self.queue, util=self.util, total_time=total)

# ─────────────────────────── Plot helpers ─────────────────────────── #
def gantt(events):
    df = pd.DataFrame(events)
    segments = []
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        rtype = rd["rider_type"].iloc[0]
        for z in ["Queue", "Gate", "ZoneA", "ZoneB", "ZoneC", "Exit"]:
            ent = rd[(rd.zone == z) & (rd.action == "enter")].reset_index()
            ext = rd[(rd.zone == z) & (rd.action == "exit")].reset_index()
            for i in range(min(len(ent), len(ext))):
                segments.append(dict(
                    Task=rid,
                    Start=ent.loc[i, "time"],
                    Finish=ext.loc[i, "time"],
                    Resource=rtype
                ))
    if not segments:
        return None
    seg_df = pd.DataFrame(segments)
    colors = {"INST": "rgb(255,0,0)", "EXP": "rgb(0,255,0)", "FOC": "rgb(0,0,255)"}
    fig = ff.create_gantt(
        seg_df, colors=colors, index_col="Resource",
        group_tasks=True, show_colorbar=True, title="Rider Timeline"
    )
    fig.update_layout(
        xaxis_title="Time (min)", yaxis_title="Rider",
        legend_title="Type", height=600
    )
    return fig

def line(df, x, y, **kw):
    if df.empty:
        return None
    return px.line(df, x=x, y=y, **kw)

# ─────────────────────────── Streamlit UI ─────────────────────────── #
def main():
    st.set_page_config("Rider Training Track Simulation", "🏍️", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # Default parameters
    defaults = dict(
        nEXP=25, nFOC=10, capZone=1,
        tEnter=0.5, tA=5.0, tB=5.0, tC=5.0, tExit=0.5
    )
    if "p" not in st.session_state:
        st.session_state.p = defaults.copy()
    p = st.session_state.p

    # Sidebar inputs
    st.sidebar.header("Parameters")
    p["nEXP"]    = st.sidebar.number_input("Experienced riders", min_value=0,   max_value=100, value=p["nEXP"])
    p["nFOC"]    = st.sidebar.number_input("Focus riders",       min_value=0,   max_value=100, value=p["nFOC"])
    p["capZone"] = st.sidebar.number_input("Capacity / zone",    min_value=1,   max_value=6,   value=p["capZone"])

    st.sidebar.subheader("Times (minutes)")
    for k, lo, hi in [
        ("tEnter", 0.0, 5.0),
        ("tA",      1.0, 20.0),
        ("tB",      1.0, 20.0),
        ("tC",      1.0, 20.0),
        ("tExit",   0.0, 5.0),
    ]:
        p[k] = st.sidebar.number_input(
            label=k,
            min_value=lo,
            max_value=hi,
            value=p[k],
            step=0.1 if k in ("tEnter", "tExit") else 0.5
        )

    # Run button
    if st.sidebar.button("Run simulation"):
        with st.spinner("Running simulation..."):
            st.session_state.res = RiderTrackSimulation(p).run()

    # Save / Load scenario
    st.sidebar.subheader("Save / load scenario")
    scen = st.sidebar.text_area("Scenario JSON", json.dumps(p, indent=2), height=160)
    if st.sidebar.button("Load"):
        try:
            st.session_state.p = json.loads(scen)
            st.sidebar.success("Loaded!")
        except json.JSONDecodeError as e:
            st.sidebar.error(f"Invalid JSON: {e}")

    # Display results
    if "res" in st.session_state:
        res = st.session_state.res
        st.success(f"Simulation completed in {res['total_time']:.2f} minutes.")

        tab1, tab2 = st.tabs(["Gantt Chart", "Statistics"])
        with tab1:
            fig = gantt(res["events"])
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No Gantt data available.")

        with tab2:
            df_q = pd.DataFrame(res["queue"])
            df_u = pd.DataFrame([
                {"time": u["time"], "zone": f"Zone {z}", "util": u["utilization"] * 100}
                for z, lst in res["util"].items() for u in lst
            ])

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Queue Length Over Time")
                fig_q = line(
                    df_q, "time", "queue_len",
                    title="Queue length", labels={"queue_len": "Riders"}
                )
                if fig_q:
                    st.plotly_chart(fig_q, use_container_width=True)
                else:
                    st.info("No queue data.")

            with col2:
                st.subheader("Zone Utilization (%)")
                fig_u = line(
                    df_u, "time", "util", color="zone",
                    title="Zone Utilization", labels={"util": "%"}
                )
                if fig_u:
                    st.plotly_chart(fig_u, use_container_width=True)
                else:
                    st.info("No utilization data.")

    else:
        st.info("Adjust parameters and click **Run simulation** to start.")

if __name__ == "__main__":
    main()
