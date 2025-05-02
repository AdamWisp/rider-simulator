# app.py
import json
import time
from datetime import datetime

import numpy as np
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

        # If user selected FOC-only, suppress EXP riders
        if self.p.get("batch") == "FOC":
            self.p["nEXP"] = 0
        # If EXP-only, suppress FOC
        if self.p.get("batch") == "EXP":
            self.p["nFOC"] = 0

        # Resources: zones A, B, C
        self.zone_a = simpy.Resource(self.env, capacity=self.p["capZone"])
        self.zone_b = simpy.Resource(self.env, capacity=self.p["capZone"])
        self.zone_c = simpy.Resource(self.env, capacity=self.p["capZone"])

        # Stats
        self.events = []
        self.queue_stats = []
        self.util_stats = {"A": [], "B": [], "C": []}

        # Synchronization events
        self.inst_done = self.env.event()
        self.exp_done = self.env.event()
        if self.p["nEXP"] == 0:
            self.exp_done.succeed()

        # Completion barrier
        self.done_event = self.env.event()
        self.total_riders = 1 + self.p["nEXP"] + self.p["nFOC"]
        self.finished = 0

        # Kick off instructor
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
            exited  = sum(e["zone"] == "Queue" and e["action"] == "exit"  for e in self.events)
            self.queue_stats.append({
                "time": self.env.now,
                "queue_length": entered - exited
            })
            yield self.env.timeout(0.5)

    def monitor_util(self, tag, res):
        while True:
            self.util_stats[tag].append({
                "time": self.env.now,
                "utilization": res.count / res.capacity
            })
            yield self.env.timeout(0.5)

    def rider(self, rid, rtype):
        # Queue
        self.record(rid, rtype, "Queue", "enter")

        # Enter Gate / Zone A
        with self.zone_a.request() as req:
            yield req
            self.record(rid, rtype, "Queue", "exit")
            self.record(rid, rtype, "Gate", "enter")
            yield self.env.timeout(self.p["tEnter"])
            self.record(rid, rtype, "Gate", "exit")
            if rtype == "INST":
                self.inst_done.succeed()

        # Zone A dwell
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

        # Exit Gate
        self.record(rid, rtype, "Exit", "enter")
        yield self.env.timeout(self.p["tExit"])
        self.record(rid, rtype, "Exit", "exit")

        # EXP completion
        if rtype == "EXP":
            done_exp = sum(1 for e in self.events
                           if e["rider_type"] == "EXP" and
                              e["zone"] == "Exit" and
                              e["action"] == "exit")
            if done_exp == self.p["nEXP"]:
                self.exp_done.succeed()

        # Check global completion
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
        # Start monitors & injectors
        self.env.process(self.monitor_queue())
        self.env.process(self.monitor_util("A", self.zone_a))
        self.env.process(self.monitor_util("B", self.zone_b))
        self.env.process(self.monitor_util("C", self.zone_c))
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())

        # Run until all complete
        self.env.run(until=self.done_event)

        total = max(e["time"] for e in self.events) if self.events else 0
        return {
            "events": self.events,
            "queue_stats": self.queue_stats,
            "util_stats": self.util_stats,
            "total_time": total
        }


# ─────────────────────────── Plot helpers ──────────────────────────── #
def create_gantt_chart(events):
    df = pd.DataFrame(events)
    tasks = []
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        rtype = rd["rider_type"].iloc[0]
        for zone in ["Queue", "Gate", "ZoneA", "ZoneB", "ZoneC", "Exit"]:
            ent = rd[(rd.zone == zone) & (rd.action == "enter")].reset_index()
            ext = rd[(rd.zone == zone) & (rd.action == "exit")].reset_index()
            for i in range(min(len(ent), len(ext))):
                tasks.append({
                    "Task": rid,
                    "Start": ent.loc[i, "time"],
                    "Finish": ext.loc[i, "time"],
                    "Resource": rtype
                })
    if not tasks:
        return None
    df_tasks = pd.DataFrame(tasks).sort_values(["Resource", "Task", "Start"])
    colors = {"INST": "rgb(255,0,0)", "EXP": "rgb(0,255,0)", "FOC": "rgb(0,0,255)"}
    fig = ff.create_gantt(
        df_tasks, colors=colors, index_col="Resource",
        group_tasks=True, show_colorbar=True, title="Rider Timeline"
    )
    fig.update_layout(
        xaxis_title="Time (min)",
        yaxis_title="Rider",
        legend_title="Type",
        height=600
    )
    return fig


def create_zone_util_chart(util_stats):
    rows = []
    for zone, lst in util_stats.items():
        for stat in lst:
            rows.append({
                "Time": stat["time"],
                "Zone": f"Zone {zone}",
                "Utilization": stat["utilization"] * 100
            })
    df = pd.DataFrame(rows)
    fig = px.line(
        df, x="Time", y="Utilization", color="Zone",
        title="Zone Utilization Over Time",
        labels={"Utilization": "% Utilization"}
    )
    fig.update_layout(yaxis_range=[0, 100])
    return fig


def create_queue_chart(queue_stats):
    df = pd.DataFrame(queue_stats)
    fig = px.line(
        df, x="time", y="queue_length",
        title="Queue Length Over Time",
        labels={"queue_length": "Riders in Queue"}
    )
    return fig


def create_animation_frame(events, current_time, params):
    zones = ["Queue", "Gate", "ZoneA", "ZoneB", "ZoneC", "Exit"]
    df = pd.DataFrame(events)
    occupancy = {z: [] for z in zones}
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        for zone in zones:
            zd = rd[rd["zone"] == zone]
            ent = zd[zd["action"] == "enter"]
            ext = zd[zd["action"] == "exit"]
            for _, e in ent.iterrows():
                start, exits = e["time"], ext[ext["time"] > e["time"]]["time"].tolist()
                end = min(exits) if exits else float("inf")
                if start <= current_time < end:
                    occupancy[zone].append(rid)
                    break

    st.write(f"Simulation Time: {current_time:.2f} min")
    cols = st.columns(6)
    for col, zone, label in zip(cols, zones,
                               ["Queue", "Gate", "Zone A", "Zone B", "Zone C", "Exit"]):
        with col:
            st.write(f"## {label}")
            for rid in occupancy[zone]:
                rtype = df[df["rider_id"] == rid]["rider_type"].iloc[0]
                icon = "🔴" if rtype == "INST" else "🟢" if rtype == "EXP" else "🔵"
                st.write(f"{icon} {rid}")

    st.write("---")
    st.write("🔴 INST | 🟢 EXP | 🔵 FOC")


def export_to_csv(results):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    events_csv = pd.DataFrame(results["events"]).to_csv(index=False)
    queue_csv  = pd.DataFrame(results["queue_stats"]).to_csv(index=False)
    util_rows = []
    for z, lst in results["util_stats"].items():
        for s in lst:
            util_rows.append({"zone": z, **s})
    util_csv   = pd.DataFrame(util_rows).to_csv(index=False)
    return {
        "events": events_csv,
        "queue": queue_csv,
        "util": util_csv,
        "ts": ts
    }


def main():
    st.set_page_config("Rider Training Track Simulation", "🏍️", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # Sidebar: parameters
    defaults = {
        "nEXP": 25, "nFOC": 10, "capZone": 1,
        "tEnter": 0.5, "tA": 5.0, "tB": 5.0, "tC": 5.0, "tExit": 0.5,
        "batch": "EXP"
    }
    if "params" not in st.session_state:
        st.session_state.params = defaults.copy()
    p = st.session_state.params

    st.sidebar.header("Simulation Parameters")
    p["batch"]   = st.sidebar.radio("Batch type", ["EXP", "FOC"], index=["EXP", "FOC"].index(p["batch"]))
    p["nEXP"]    = st.sidebar.number_input("Number of EXP Riders", min_value=1,   max_value=100, value=p["nEXP"])
    p["nFOC"]    = st.sidebar.number_input("Number of FOC Riders", min_value=0,   max_value=100, value=p["nFOC"])
    p["capZone"] = st.sidebar.number_input("Riders per Zone",      min_value=1,   max_value=6,   value=p["capZone"])

    st.sidebar.subheader("Time Parameters (min)")
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

    if st.sidebar.button("Run Simulation"):
        with st.spinner("Simulating..."):
            st.session_state.results = RiderTrackSimulation(p).run()
            st.session_state.animate = False

    st.sidebar.subheader("Save / Load Scenario")
    scen = st.sidebar.text_area("Scenario JSON", json.dumps(p, indent=2), height=160)
    if st.sidebar.button("Load"):
        try:
            st.session_state.params = json.loads(scen)
            st.sidebar.success("Loaded!")
        except json.JSONDecodeError as e:
            st.sidebar.error(f"Invalid JSON: {e}")

    # Show results & visuals
    if "results" in st.session_state:
        res = st.session_state.results
        st.header("Simulation Results")
        st.write(f"**Total time:** {res['total_time']:.2f} min")

        # Export
        csvs = export_to_csv(res)
        st.download_button("Download Events CSV", csvs["events"], f"events_{csvs['ts']}.csv")
        st.download_button("Download Queue CSV",  csvs["queue"],  f"queue_{csvs['ts']}.csv")
        st.download_button("Download Util CSV",   csvs["util"],   f"util_{csvs['ts']}.csv")

        # Tabs: Gantt, Util, Queue, Animation
        tab1, tab2, tab3, tab4 = st.tabs(["Gantt Chart", "Zone Utilization", "Queue Length", "Animation"])
        with tab1:
            fig = create_gantt_chart(res["events"])
            st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")
        with tab2:
            fig = create_zone_util_chart(res["util_stats"])
            st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")
        with tab3:
            fig = create_queue_chart(res["queue_stats"])
            st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")
        with tab4:
            # Animation controls
            if st.button("Start Animation" if not st.session_state.animate else "Stop Animation"):
                st.session_state.animate = not st.session_state.animate
            speed = st.slider("Animation Speed", 0.1, 5.0, 1.0, 0.1)
            if st.session_state.animate:
                total_t = res["total_time"]
                progress = st.progress(0)
                container = st.empty()
                dt = 0.5 / speed
                t = 0.0
                while t <= total_t and st.session_state.animate:
                    progress.progress(min(t/total_t, 1.0))
                    with container:
                        create_animation_frame(res["events"], t, p)
                    time.sleep(0.1)
                    t += dt
            else:
                create_animation_frame(res["events"], 0.0, p)

    else:
        st.info("Configure parameters and click **Run Simulation** to begin.")


if __name__ == "__main__":
    main()
