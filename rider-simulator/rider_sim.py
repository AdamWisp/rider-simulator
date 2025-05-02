import json
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import simpy
import streamlit as st


# ─────────────────────────── Simulation core ──────────────────────────── #
class RiderTrackSimulation:
    def __init__(self, params: dict):
        self.env = simpy.Environment()
        self.p = params.copy()

        # Zone resources
        self.zone_a = simpy.Resource(self.env, capacity=self.p["capZone"])
        self.zone_b = simpy.Resource(self.env, capacity=self.p["capZone"])
        self.zone_c = simpy.Resource(self.env, capacity=self.p["capZone"])

        # Stats
        self.events = []
        self.queue_stats = []
        self.util_stats = {"A": [], "B": [], "C": []}

        # Sync events
        self.inst_done = self.env.event()
        self.exp_done = self.env.event()
        if self.p["nEXP"] == 0:
            self.exp_done.succeed()

        # Completion barrier
        self.done_event = self.env.event()
        self.total_riders = 1 + self.p["nEXP"] + self.p["nFOC"]
        self.finished = 0

        # Kick off
        self.env.process(self.rider("INST-1", "INST"))

    def record(self, rider_id, rider_type, zone, action):
        self.events.append({
            "rider_id": rider_id,
            "rider_type": rider_type,
            "zone": zone,
            "action": action,
            "time": self.env.now
        })

    def monitor_queue(self):
        while True:
            entered = sum(e["zone"] == "Queue" and e["action"] == "enter" for e in self.events)
            exited = sum(e["zone"] == "Queue" and e["action"] == "exit" for e in self.events)
            self.queue_stats.append({"time": self.env.now, "queue_length": entered - exited})
            yield self.env.timeout(0.5)

    def monitor_util(self, tag, res):
        while True:
            self.util_stats[tag].append({
                "time": self.env.now,
                "utilization": res.count / res.capacity
            })
            yield self.env.timeout(0.5)

    def rider(self, rid, rtype):
        self.record(rid, rtype, "Queue", "enter")

        # Enter gate / Zone A
        with self.zone_a.request() as req:
            yield req
            self.record(rid, rtype, "Queue", "exit")
            self.record(rid, rtype, "Gate", "enter")
            yield self.env.timeout(self.p["tEnter"])
            self.record(rid, rtype, "Gate", "exit")
            if rtype == "INST" and not self.inst_done.triggered:
                # only succeed after full exit below
                pass

        # Zone A
        self.record(rid, rtype, "ZoneA", "enter")
        yield self.env.timeout(self.p["tA"])
        self.record(rid, rtype, "ZoneA", "exit")

        # Zone B
        with self.zone_b.request() as req:
            yield req
            self.record(rid, rtype, "ZoneB", "enter")
            yield self.env.timeout(self.p["tB"])
            self.record(rid, rtype, "ZoneB", "exit")

        # Zone C
        with self.zone_c.request() as req:
            yield req
            self.record(rid, rtype, "ZoneC", "enter")
            yield self.env.timeout(self.p["tC"])
            self.record(rid, rtype, "ZoneC", "exit")

        # Exit gate
        self.record(rid, rtype, "Exit", "enter")
        yield self.env.timeout(self.p["tExit"])
        self.record(rid, rtype, "Exit", "exit")

        # Trigger inst_done now that instructor fully exited
        if rtype == "INST" and not self.inst_done.triggered:
            self.inst_done.succeed()

        # Trigger exp_done when all EXP have exited
        if rtype == "EXP":
            done_exp = sum(1 for e in self.events
                           if e["rider_type"] == "EXP" and e["zone"] == "Exit" and e["action"] == "exit")
            if done_exp == self.p["nEXP"] and not self.exp_done.triggered:
                self.exp_done.succeed()

        # Completion counter
        self.finished += 1
        if self.finished == self.total_riders and not self.done_event.triggered:
            self.done_event.succeed()

    def inject_exp(self):
        yield self.inst_done
        for i in range(1, self.p["nEXP"] + 1):
            self.env.process(self.rider(f"EXP-{i}", "EXP"))

    def inject_foc(self):
        yield self.exp_done
        for i in range(1, self.p["nFOC"] + 1):
            self.env.process(self.rider(f"FOC-{i}", "FOC"))

    def run(self):
        self.env.process(self.monitor_queue())
        self.env.process(self.monitor_util("A", self.zone_a))
        self.env.process(self.monitor_util("B", self.zone_b))
        self.env.process(self.monitor_util("C", self.zone_c))
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())
        self.env.run(until=self.done_event)
        total_time = max(e["time"] for e in self.events) if self.events else 0
        return {"events": self.events, "queue": self.queue_stats, "util": self.util_stats, "total_time": total_time}


# ─────────────────────────── Plot helpers ──────────────────────────── #
def create_simplified_gantt(events):
    df = pd.DataFrame(events)
    tasks = []
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        for zone in ["ZoneA", "ZoneB", "ZoneC"]:
            ent = rd[(rd.zone == zone) & (rd.action == "enter")].reset_index()
            ext = rd[(rd.zone == zone) & (rd.action == "exit")].reset_index()
            for i in range(min(len(ent), len(ext))):
                tasks.append({
                    "Task": rid,
                    "Start": ent.loc[i, "time"],
                    "Finish": ext.loc[i, "time"],
                    "Resource": zone
                })
    if not tasks:
        return None
    tdf = pd.DataFrame(tasks).sort_values(["Resource", "Task", "Start"])
    colors = {"ZoneA": "#FFA07A", "ZoneB": "#20B2AA", "ZoneC": "#9370DB"}
    fig = ff.create_gantt(tdf, colors=colors, index_col="Resource", group_tasks=True,
                          show_colorbar=True, title="Zones A→B→C Timeline")
    fig.update_layout(xaxis_title="Time (min)", yaxis_title="Rider", legend_title="Zone", height=500)
    return fig

def create_animation_frame(events, current_time):
    df = pd.DataFrame(events)
    zones = ["Queue", "Gate", "ZoneA", "ZoneB", "ZoneC", "Exit"]
    occupancy = {z: [] for z in zones}
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        for z in zones:
            ent = rd[(rd.zone == z) & (rd.action == "enter")]
            ext = rd[(rd.zone == z) & (rd.action == "exit")]
            for _, e in ent.iterrows():
                start = e.time
                exit_times = ext[ext.time > start].time.tolist()
                end = min(exit_times) if exit_times else float("inf")
                if start <= current_time < end:
                    occupancy[z].append(rid)
                    break
    st.write(f"Time = {current_time:.2f} min")
    cols = st.columns(6)
    labels = ["Queue", "Gate", "Zone A", "Zone B", "Zone C", "Exit"]
    for col, z, lbl in zip(cols, zones, labels):
        with col:
            st.write(f"## {lbl}")
            for rider in occupancy[z]:
                rtype = df[df.rider_id == rider].rider_type.iloc[0]
                icon = "🔴" if rtype == "INST" else "🟢" if rtype == "EXP" else "🔵"
                st.write(f"{icon} {rider}")
    st.write("---")
    st.write("🔴 INST | 🟢 EXP | 🔵 FOC")


def main():
    st.set_page_config(page_title="Rider Simulator", layout="wide")
    st.title("🏍️ Rider Training Track")

    defaults = {"batch": "EXP", "nEXP": 25, "nFOC": 10, "capZone": 1,
                "tEnter": 0.5, "tA": 5.0, "tB": 5.0, "tC": 5.0, "tExit": 0.5}
    if "params" not in st.session_state:
        st.session_state.params = defaults.copy()
    p = st.session_state.params

    st.sidebar.header("Configuration")
    p["batch"]   = st.sidebar.radio("Batch to run", ["EXP", "FOC"], index=["EXP","FOC"].index(p["batch"]))
    p["nEXP"]    = st.sidebar.number_input("EXP riders", min_value=0, max_value=100, value=p["nEXP"])
    p["nFOC"]    = st.sidebar.number_input("FOC riders", min_value=0, max_value=100, value=p["nFOC"])
    p["capZone"] = st.sidebar.number_input("Zones capacity", min_value=1, max_value=6, value=p["capZone"])

    st.sidebar.subheader("Durations (minutes)")
    for key, lo, hi in [("tEnter",0.0,5.0), ("tA",1.0,20.0), ("tB",1.0,20.0), ("tC",1.0,20.0), ("tExit",0.0,5.0)]:
        p[key] = st.sidebar.number_input(label=key, min_value=lo, max_value=hi, value=p[key], step=0.1 if key in ("tEnter","tExit") else 0.5)

    if st.sidebar.button("Run Simulation"):
        with st.spinner("Simulating..."):
            st.session_state.results = RiderTrackSimulation(p).run()
            st.session_state.animate = False

    st.sidebar.subheader("Save/Load Scenario")
    scen = st.sidebar.text_area("Scenario JSON", json.dumps(p, indent=2), height=150)
    if st.sidebar.button("Load"):
        try:
            st.session_state.params = json.loads(scen)
            st.sidebar.success("Loaded")
        except json.JSONDecodeError as e:
            st.sidebar.error(e)

    if "results" in st.session_state:
        res = st.session_state.results
        st.success(f"Total session time: {res['total_time']:.2f} min")

        # Batch finish times
        inst_finish = max(e['time'] for e in res['events'] if e['rider_id']=='INST-1' and e['zone']=='Exit' and e['action']=='exit')
        exp_finish = max((e['time'] for e in res['events'] if e['rider_type']=='EXP' and e['zone']=='Exit' and e['action']=='exit'), default=0)
        foc_finish = max((e['time'] for e in res['events'] if e['rider_type']=='FOC' and e['zone']=='Exit' and e['action']=='exit'), default=0)
        st.write(f"Instructor finish: {inst_finish:.2f} min | EXP finish: {exp_finish:.2f} min | FOC finish: {foc_finish:.2f} min")

        # Gantt
        st.subheader("Zone-wise Gantt")
        gantt_fig = create_simplified_gantt(res['events'])
        if gantt_fig:
            st.plotly_chart(gantt_fig, use_container_width=True)
        else:
            st.info("No Gantt data")

        # Animation
        st.subheader("Live Animation")
        if st.button("Start/Stop Animation"):
            st.session_state.animate = not st.session_state.animate
        speed = st.slider("Speed", 0.1, 5.0, 1.0, 0.1)
        if st.session_state.animate:
            total = res['total_time']
            progress = st.progress(0)
            container = st.empty()
            t = 0.0
            dt = 0.5 / speed
            while t <= total and st.session_state.animate:
                progress.progress(min(t/total,1.0))
                with container:
                    create_animation_frame(res['events'], t)
                time.sleep(0.1)
                t += dt
        else:
            create_animation_frame(res['events'], 0.0)
    else:
        st.info("Configure parameters and run simulation.")


if __name__ == "__main__":
    main()
