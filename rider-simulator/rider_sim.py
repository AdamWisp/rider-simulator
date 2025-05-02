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


# ───────────────────────────── Simulation core ────────────────────────────── #
class RiderTrackSimulation:
    def __init__(self, params: dict):
        self.env = simpy.Environment()
        self.params = params

        # Resources (zones)
        self.zone_a = simpy.Resource(self.env, capacity=params["capZone"])
        self.zone_b = simpy.Resource(self.env, capacity=params["capZone"])
        self.zone_c = simpy.Resource(self.env, capacity=params["capZone"])

        # Stats
        self.rider_events = []
        self.queue_stats = []
        self.zone_stats = {"A": [], "B": [], "C": []}
        self.riders_in_queue = 0

        # Synchronisation events
        self.inst_done = self.env.event()
        self.exp_done = self.env.event()
        if params["nEXP"] == 0:  # nothing to wait for
            self.exp_done.succeed()

        # Completion bookkeeping
        self.total_riders = 1 + params["nEXP"] + params["nFOC"]
        self.finished_riders = 0

        # Kick off first process (Instructor)
        self.env.process(self.rider_process("INST-1", "INST"))

    # ----------------------- bookkeeping helpers --------------------------- #
    def record_event(self, rider_id, rider_type, zone, action, t):
        self.rider_events.append(
            {"rider_id": rider_id, "rider_type": rider_type, "zone": zone, "action": action, "time": t}
        )

    def track_queue(self):
        while True:
            self.queue_stats.append({"time": self.env.now, "queue_length": self.riders_in_queue})
            yield self.env.timeout(0.5)

    def track_zone_utilization(self, zone_name, resource):
        while True:
            self.zone_stats[zone_name].append(
                {"time": self.env.now, "utilization": resource.count / resource.capacity}
            )
            yield self.env.timeout(0.5)

    # ----------------------- main rider process --------------------------- #
    def rider_process(self, rider_id, rider_type):
        arrival_time = self.env.now
        self.riders_in_queue += 1
        self.record_event(rider_id, rider_type, "Queue", "enter", self.env.now)

        # ---- Enter gate -------------------------------------------------- #
        with self.zone_a.request() as req:
            yield req
            self.riders_in_queue -= 1
            self.record_event(rider_id, rider_type, "Queue", "exit", self.env.now)
            self.record_event(rider_id, rider_type, "EnterGate", "enter", self.env.now)
            yield self.env.timeout(self.params["tEnter"])
            self.record_event(rider_id, rider_type, "EnterGate", "exit", self.env.now)

            if rider_type == "INST":
                self.inst_done.succeed()

        # ---- Zone A ------------------------------------------------------ #
        self.record_event(rider_id, rider_type, "ZoneA", "enter", self.env.now)
        yield self.env.timeout(self.params["tA"])
        self.record_event(rider_id, rider_type, "ZoneA", "exit", self.env.now)

        # ---- Zone B ------------------------------------------------------ #
        with self.zone_b.request() as req:
            yield req
            self.record_event(rider_id, rider_type, "ZoneB", "enter", self.env.now)
            yield self.env.timeout(self.params["tB"])
            self.record_event(rider_id, rider_type, "ZoneB", "exit", self.env.now)

        # ---- Zone C ------------------------------------------------------ #
        with self.zone_c.request() as req:
            yield req
            self.record_event(rider_id, rider_type, "ZoneC", "enter", self.env.now)
            yield self.env.timeout(self.params["tC"])
            self.record_event(rider_id, rider_type, "ZoneC", "exit", self.env.now)

        # ---- Exit gate --------------------------------------------------- #
        self.record_event(rider_id, rider_type, "ExitGate", "enter", self.env.now)
        yield self.env.timeout(self.params["tExit"])
        self.record_event(rider_id, rider_type, "ExitGate", "exit", self.env.now)

        # ---- rider finished --------------------------------------------- #
        if rider_type == "EXP":
            # last EXP to exit?  mark exp_done.
            completed_exp = len([e for e in self.rider_events if e["rider_type"] == "EXP" and e["zone"] == "ExitGate" and e["action"] == "exit"])
            if completed_exp == self.params["nEXP"]:
                self.exp_done.succeed()

        self.finished_riders += 1
        if self.finished_riders == self.total_riders:
            self.env.exit()  # terminate whole simulation

    # ----------------------- injection helpers --------------------------- #
    def inject_exp_riders(self):
        yield self.inst_done  # wait instructor
        for i in range(1, self.params["nEXP"] + 1):
            self.env.process(self.rider_process(f"EXP-{i}", "EXP"))

    def inject_foc_riders(self):
        yield self.exp_done  # wait last EXP
        for i in range(1, self.params["nFOC"] + 1):
            self.env.process(self.rider_process(f"FOC-{i}", "FOC"))

    # ----------------------- public runner ------------------------------- #
    def run(self):
        # Background monitors
        self.env.process(self.track_queue())
        self.env.process(self.track_zone_utilization("A", self.zone_a))
        self.env.process(self.track_zone_utilization("B", self.zone_b))
        self.env.process(self.track_zone_utilization("C", self.zone_c))

        # Inject batches
        self.env.process(self.inject_exp_riders())
        self.env.process(self.inject_foc_riders())

        self.env.run()  # ends when self.env.exit() is called

        total_time = max(e["time"] for e in self.rider_events) if self.rider_events else 0
        return {
            "events": self.rider_events,
            "queue_stats": self.queue_stats,
            "zone_stats": self.zone_stats,
            "total_time": total_time,
        }


# ───────────────────────────── Plotting helpers ───────────────────────────── #
def create_gantt_chart(events):
    df = pd.DataFrame(events)
    tasks = []
    for r in df["rider_id"].unique():
        rd = df[df["rider_id"] == r]
        r_type = rd["rider_type"].iloc[0]
        for zone in ["Queue", "EnterGate", "ZoneA", "ZoneB", "ZoneC", "ExitGate"]:
            zd = rd[rd["zone"] == zone]
            enters = zd[zd["action"] == "enter"].reset_index(drop=True)
            exits = zd[zd["action"] == "exit"].reset_index(drop=True)
            for i in range(min(len(enters), len(exits))):
                tasks.append(
                    dict(Task=r, Start=enters.loc[i, "time"], Finish=exits.loc[i, "time"], Resource=zone, Type=r_type)
                )
    if not tasks:
        return None
    tasks_df = pd.DataFrame(tasks).sort_values(["Type", "Task", "Start"])
    colors = {"INST": "rgb(255,0,0)", "EXP": "rgb(0,255,0)", "FOC": "rgb(0,0,255)"}
    fig = ff.create_gantt(tasks_df, colors=colors, index_col="Resource", group_tasks=True, show_colorbar=True,
                          title="Rider Training Track Simulation")
    fig.update_layout(xaxis_title="Time (min)", yaxis_title="Rider", legend_title="Rider Type", height=600)
    return fig


def create_zone_utilization_chart(zone_stats):
    rows = [{"Time": s["time"], "Zone": f"Zone {z}", "Utilization": s["utilization"] * 100}
            for z, lst in zone_stats.items() for s in lst]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    fig = px.line(df, x="Time", y="Utilization", color="Zone", title="Zone Utilization",
                  labels={"Utilization": "Utilization (%)"})
    fig.update_layout(yaxis_range=[0, 100])
    return fig


def create_queue_length_chart(queue_stats):
    if not queue_stats:
        return None
    df = pd.DataFrame(queue_stats)
    fig = px.line(df, x="time", y="queue_length", title="Queue Length")
    fig.update_layout(xaxis_title="Time (min)", yaxis_title="Riders in Queue")
    return fig


# ────────────────────────────── Streamlit UI ──────────────────────────────── #
def export_to_csv(results):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "events": pd.DataFrame(results["events"]).to_csv(index=False),
        "queue": pd.DataFrame(results["queue_stats"]).to_csv(index=False),
        "zone": pd.DataFrame(
            [{"zone": z, **s} for z, lst in results["zone_stats"].items() for s in lst]
        ).to_csv(index=False),
        "ts": ts,
    }


def run_simulation(params):
    return RiderTrackSimulation(params).run()


def main():
    st.set_page_config("Rider Training Track Simulation", "🏍️", "wide")
    st.title("🏍️ Rider Training Track Simulation")

    # ---- Sidebar inputs -------------------------------------------------- #
    st.sidebar.header("Parameters")
    defaults = {
        "nEXP": 25, "nFOC": 10, "capZone": 1,
        "tEnter": 0.5, "tA": 5.0, "tB": 5.0, "tC": 5.0, "tExit": 0.5
    }
    if "params" not in st.session_state:
        st.session_state.params = defaults.copy()
    p = st.session_state.params

    p["nEXP"] = st.sidebar.number_input("Experienced riders", 0, 100, p["nEXP"])
    p["nFOC"] = st.sidebar.number_input("Focus riders", 0, 100, p["nFOC"])
    p["capZone"] = st.sidebar.number_input("Capacity / zone", 1, 6, p["capZone"])
    st.sidebar.subheader("Times (minutes)")
    p["tEnter"] = st.sidebar.number_input("Enter gate", 0.0, 5.0, p["tEnter"], 0.1)
    p["tA"] = st.sidebar.number_input("Zone A dwell", 1.0, 20.0, p["tA"], 0.5)
    p["tB"] = st.sidebar.number_input("Zone B dwell", 1.0, 20.0, p["tB"], 0.5)
    p["tC"] = st.sidebar.number_input("Zone C dwell", 1.0, 20.0, p["tC"], 0.5)
    p["tExit"] = st.sidebar.number_input("Exit gate", 0.0, 5.0, p["tExit"], 0.1)

    if st.sidebar.button("Run simulation"):
        with st.spinner("Simulating…"):
            st.session_state.results = run_simulation(p.copy())
            st.session_state.animate = False

    # ---- Save / load ----------------------------------------------------- #
    st.sidebar.subheader("Save / load scenario")
    scenario_str = st.sidebar.text_area("Scenario JSON", json.dumps(p, indent=2), height=150)
    if st.sidebar.button("Load"):
        try:
            st.session_state.params = json.loads(scenario_str)
            st.sidebar.success("Loaded!")
        except json.JSONDecodeError as e:
            st.sidebar.error(f"Invalid JSON: {e}")

    # ---- Results --------------------------------------------------------- #
    if "results" in st.session_state and st.session_state.results:
        res = st.session_state.results
        st.header("Results")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Summary")
            st.write(f"Total time : **{res['total_time']:.2f} min**")
            st.write(f"EXP / FOC : {p['nEXP']} / {p['nFOC']}")
            st.write(f"Capacity  : {p['capZone']} per zone")
        with c2:
            st.subheader("Export")
            csvs = export_to_csv(res)
            st.download_button("Events CSV", csvs["events"], f"events_{csvs['ts']}.csv", "text/csv")
            st.download_button("Queue CSV", csvs["queue"], f"queue_{csvs['ts']}.csv", "text/csv")
            st.download_button("Zone CSV", csvs["zone"], f"zone_{csvs['ts']}.csv", "text/csv")

        # ---- Visuals ---------------------------------------------------- #
        tab1, tab2, tab3 = st.tabs(["Gantt", "Utilization", "Queue"])
        with tab1:
            gfig = create_gantt_chart(res["events"])
            st.plotly_chart(gfig, use_container_width=True) if gfig else st.info("No data")
        with tab2:
            ufig = create_zone_utilization_chart(res["zone_stats"])
            st.plotly_chart(ufig, use_container_width=True) if ufig else st.info("No data")
        with tab3:
            qfig = create_queue_length_chart(res["queue_stats"])
            st.plotly_chart(qfig, use_container_width=True) if qfig else st.info("No data")
    else:
        st.info("Set parameters in the sidebar and click *Run simulation*.")


if __name__ == "__main__":
    main()
