# app.py  – clean, working 2 May 2025
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
        self.events.append(dict(rider_id=rid, rider_type=rtype,
                                zone=zone, action=action, time=self.env.now))

    def monitor_queue(self):
        while True:
            self.queue.append(dict(time=self.env.now,
                                   queue_len=sum(e["zone"] == "Queue" and e["action"] == "enter"
                                                 for e in self.events) -
                                             sum(e["zone"] == "Queue" and e["action"] == "exit"
                                                 for e in self.events)))
            yield self.env.timeout(0.5)

    def monitor_util(self, tag, res):
        while True:
            self.util[tag].append(dict(time=self.env.now,
                                       utilization=res.count / res.capacity))
            yield self.env.timeout(0.5)

    # ---------------- main rider process ---------------- #
    def rider(self, rid, rtype):
        self.rec(rid, rtype, "Queue", "enter")

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

        # Exit
        self.rec(rid, rtype, "Exit", "enter")
        yield self.env.timeout(self.p["tExit"])
        self.rec(rid, rtype, "Exit", "exit")

        # bookkeeping
        if rtype == "EXP":
            if len([e for e in self.events if e["rider_type"] == "EXP" and
                                            e["zone"] == "Exit" and
                                            e["action"] == "exit"]) == self.p["nEXP"]:
                self.exp_done.succeed()

        self.finished += 1
        if self.finished == self.total_riders and not self.done_event.triggered:
            self.done_event.succeed()

    # ---------------- injectors ---------------- #
    def inject_exp(self):
        yield self.inst_done
        for i in range(1, self.p["nEXP"] + 1):
            self.env.process(self.rider(f"EXP-{i}", "EXP"))

    def inject_foc(self):
        yield self.exp_done
        for i in range(1, self.p["nFOC"] + 1):
            self.env.process(self.rider(f"FOC-{i}", "FOC"))

    # ---------------- run ---------------- #
    def run(self):
        self.env.process(self.monitor_queue())
        self.env.process(self.monitor_util("A", self.zone_a))
        self.env.process(self.monitor_util("B", self.zone_b))
        self.env.process(self.monitor_util("C", self.zone_c))
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())

        self.env.run(until=self.done_event)      # ← stops cleanly

        total = max(e["time"] for e in self.events)
        return dict(events=self.events, queue=self.queue, util=self.util,
                    total_time=total)

# ─────────────────────────── Plot helpers ─────────────────────────── #
def gantt(events):
    df = pd.DataFrame(events)
    segs = []
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        tp = rd["rider_type"].iloc[0]
        for z in ["Queue", "Gate", "ZoneA", "ZoneB", "ZoneC", "Exit"]:
            ent = rd[(rd.zone == z) & (rd.action == "enter")]
            ext = rd[(rd.zone == z) & (rd.action == "exit")]
            for i in range(min(len(ent), len(ext))):
                segs.append(dict(Task=rid, Start=ent.iloc[i].time,
                                 Finish=ext.iloc[i].time,
                                 Resource=tp))
    if not segs:
        return None
    colors = {"INST": "rgb(255,0,0)", "EXP": "rgb(0,255,0)", "FOC": "rgb(0,0,255)"}
    fig = ff.create_gantt(pd.DataFrame(segs), colors=colors,
                          index_col="Resource", group_tasks=True,
                          show_colorbar=True, title="Rider timeline")
    fig.update_layout(xaxis_title="Minutes", yaxis_title="Rider",
                      legend_title="Type", height=600)
    return fig

def line(df, x, y, **kw):
    if df.empty:
        return None
    return px.line(df, x=x, y=y, **kw)

# ─────────────────────────── Streamlit UI ─────────────────────────── #
def main():
    st.set_page_config("Rider Track Simulator", "🏍️", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    defaults = dict(nEXP=25, nFOC=10, capZone=1,
                    tEnter=0.5, tA=5.0, tB=5.0, tC=5.0, tExit=0.5)
    if "p" not in st.session_state:
        st.session_state.p = defaults.copy()
    p = st.session_state.p

    # sidebar
    st.sidebar.header("Parameters")
    p["nEXP"]  = st.sidebar.number_input("Experienced riders", 0, 100, p["nEXP"])
    p["nFOC"]  = st.sidebar.number_input("Focus riders", 0, 100, p["nFOC"])
    p["capZone"] = st.sidebar.number_input("Capacity / zone", 1, 6, p["capZone"])
    st.sidebar.subheader("Times (min)")
    for k, lo, hi in [("tEnter",0,5), ("tA",1,20), ("tB",1,20),
                      ("tC",1,20), ("tExit",0,5)]:
        p[k] = st.sidebar.number_input(k, lo, hi, p[k], 0.1 if k in ("tEnter","tExit") else 0.5)

    if st.sidebar.button("Run simulation"):
        with st.spinner("Running..."):
            st.session_state.res = RiderTrackSimulation(p).run()

    # load / save json
    st.sidebar.subheader("Save / load")
    scen = st.sidebar.text_area("Scenario JSON", json.dumps(p, indent=2), height=160)
    if st.sidebar.button("Load"):
        try:
            st.session_state.p = json.loads(scen)
            st.sidebar.success("Loaded ✓")
        except json.JSONDecodeError as e:
            st.sidebar.error(e)

    # results
    if "res" in st.session_state:
        res = st.session_state.res
        st.success(f"Simulation finished in {res['total_time']:.2f} minutes.")
        t1, t2 = st.tabs(["Gantt", "Stats"])
        with t1:
            g = gantt(res["events"])
            st.plotly_chart(g, use_container_width=True) if g else st.info("No data.")
        with t2:
            q_df = pd.DataFrame(res["queue"])
            u_df = pd.DataFrame([{"time":u["time"], "zone":f"Zone {z}",
                                  "util":u["util"]*100}
                                  for z,l in res["util"].items() for u in l])
            l1, l2 = st.columns(2)
            with l1:
                st.subheader("Queue length")
                fig = line(q_df, "time", "queue_len",
                           title="Queue length over time",
                           labels={"queue_len":"Riders"})
                st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")
            with l2:
                st.subheader("Zone utilisation %")
                fig = line(u_df, "time", "util", color="zone",
                           title="Zone utilisation",
                           labels={"util":"% utilisation"})
                st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")

if __name__ == "__main__":
    main()
