# app.py
import json
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
        if params["nEXP"] == 0:
            self.exp_done.succeed()  # no EXP riders to wait for

        # Completion bookkeeping
        self.total_riders = 1 + params["nEXP"] + params["nFOC"]
        self.finished_riders = 0

        # Kick off instructor
        self.env.process(self.rider_process("INST-1", "INST"))

    # ---------------------------- helpers ---------------------------------- #
    def record_event(self, rider_id, rider_type, zone, action, t):
        self.rider_events.append(
            dict(rider_id=rider_id, rider_type=rider_type, zone=zone, action=action, time=t)
        )

    def track_queue(self):
        while True:
            self.queue_stats.append(dict(time=self.env.now, queue_length=self.riders_in_queue))
            yield self.env.timeout(0.5)

    def track_zone_util(self, tag, res):
        while True:
            self.zone_stats[tag].append(dict(time=self.env.now, utilization=res.count / res.capacity))
            yield self.env.timeout(0.5)

    # --------------------------- main process ------------------------------ #
    def rider_process(self, rid, rtype):
        self.riders_in_queue += 1
        self.record_event(rid, rtype, "Queue", "enter", self.env.now)

        # ---- Enter gate -------------------------------------------------- #
        with self.zone_a.request() as req:
            yield req
            self.riders_in_queue -= 1
            self.record_event(rid, rtype, "Queue", "exit", self.env.now)
            self.record_event(rid, rtype, "EnterGate", "enter", self.env.now)
            yield self.env.timeout(self.params["tEnter"])
            self.record_event(rid, rtype, "EnterGate", "exit", self.env.now)

            if rtype == "INST":
                self.inst_done.succeed()

        # ---- Zone A ------------------------------------------------------ #
        self.record_event(rid, rtype, "ZoneA", "enter", self.env.now)
        yield self.env.timeout(self.params["tA"])
        self.record_event(rid, rtype, "ZoneA", "exit", self.env.now)

        # ---- Zone B ------------------------------------------------------ #
        with self.zone_b.request() as req:
            yield req
            self.record_event(rid, rtype, "ZoneB", "enter", self.env.now)
            yield self.env.timeout(self.params["tB"])
            self.record_event(rid, rtype, "ZoneB", "exit", self.env.now)

        # ---- Zone C ------------------------------------------------------ #
        with self.zone_c.request() as req:
            yield req
            self.record_event(rid, rtype, "ZoneC", "enter", self.env.now)
            yield self.env.timeout(self.params["tC"])
            self.record_event(rid, rtype, "ZoneC", "exit", self.env.now)

        # ---- Exit gate --------------------------------------------------- #
        self.record_event(rid, rtype, "ExitGate", "enter", self.env.now)
        yield self.env.timeout(self.params["tExit"])
        self.record_event(rid, rtype, "ExitGate", "exit", self.env.now)

        # ---- bookkeeping ------------------------------------------------- #
        if rtype == "EXP":
            done_exp = len(
                [e for e in self.rider_events
                 if e["rider_type"] == "EXP" and e["zone"] == "ExitGate" and e["action"] == "exit"]
            )
            if done_exp == self.params["nEXP"]:
                self.exp_done.succeed()

        self.finished_riders += 1
        if self.finished_riders == self.total_riders:
            # Hand StopSimulation event to scheduler → env.run() ends neatly
            yield self.env.exit()

    # ----------------------- batch injectors ------------------------------ #
    def inject_exp(self):
        yield self.inst_done
        for i in range(1, self.params["nEXP"] + 1):
            self.env.process(self.rider_process(f"EXP-{i}", "EXP"))

    def inject_foc(self):
        yield self.exp_done
        for i in range(1, self.params["nFOC"] + 1):
            self.env.process(self.rider_process(f"FOC-{i}", "FOC"))

    # ------------------------------ run ----------------------------------- #
    def run(self):
        # monitors
        self.env.process(self.track_queue())
        self.env.process(self.track_zone_util("A", self.zone_a))
        self.env.process(self.track_zone_util("B", self.zone_b))
        self.env.process(self.track_zone_util("C", self.zone_c))

        # injections
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())

        self.env.run()  # stops via env.exit()

        total_time = max(e["time"] for e in self.rider_events) if self.rider_events else 0
        return dict(events=self.rider_events,
                    queue_stats=self.queue_stats,
                    zone_stats=self.zone_stats,
                    total_time=total_time)


# ───────────────────────────── Plotting helpers ───────────────────────────── #
def create_gantt_chart(events):
    df = pd.DataFrame(events)
    tasks = []
    for rid in df["rider_id"].unique():
        rd = df[df["rider_id"] == rid]
        rtype = rd["rider_type"].iloc[0]
        for z in ["Queue", "EnterGate", "ZoneA", "ZoneB", "ZoneC", "ExitGate"]:
            zd = rd[rd["zone"] == z]
            ent = zd[zd["action"] == "enter"].reset_index(drop=True)
            ext = zd[zd["action"] == "exit"].reset_index(drop=True)
            for i in range(min(len(ent), len(ext))):
                tasks.append(dict(Task=rid, Start=ent.loc[i, "time"],
                                  Finish=ext.loc[i, "time"], Resource=z, Type=rtype))
    if not tasks:
        return None
    df_tasks = pd.DataFrame(tasks).sort_values(["Type", "Task", "Start"])
    colors = {"INST": "rgb(255,0,0)", "EXP": "rgb(0,255,0)", "FOC": "rgb(0,0,255)"}
    fig = ff.create_gantt(df_tasks, colors=colors, index_col="Resource",
                          group_tasks=True, show_colorbar=True,
                          title="Rider-track simulation")
    fig.update_layout(xaxis_title="Time (min)", yaxis_title="Rider",
                      legend_title="Type", height=600)
    return fig


def create_line(df, x, y, **kwargs):
    fig = px.line(df, x=x, y=y, **kwargs)
    return fig


# ────────────────────────────── Streamlit UI ──────────────────────────────── #
def export_csv(res):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return dict(
        events=pd.DataFrame(res["events"]).to_csv(index=False),
        queue=pd.DataFrame(res["queue_stats"]).to_csv(index=False),
        zone=pd.DataFrame(
            [{"zone": z, **s} for z, lst in res["zone_stats"].items() for s in lst]
        ).to_csv(index=False),
        ts=ts,
    )


def run_sim(params):
    return RiderTrackSimulation(params).run()


def main():
    st.set_page_config("Rider Training Track Simulation", "🏍️", "wide")
    st.title("🏍️ Rider Training Track Simulation")

    # Sidebar
    st.sidebar.header("Parameters")
    defaults = dict(nEXP=25, nFOC=10, capZone=1,
                    tEnter=0.5, tA=5.0, tB=5.0, tC=5.0, tExit=0.5)
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
            st.session_state.results = run_sim(p.copy())

    # Save / load
    st.sidebar.subheader("Save / load scenario")
    scen = st.sidebar.text_area("JSON", json.dumps(p, indent=2), height=160)
    if st.sidebar.button("Load"):
        try:
            st.session_state.params = json.loads(scen)
            st.sidebar.success("Loaded ✓")
        except json.JSONDecodeError as e:
            st.sidebar.error(f"Bad JSON: {e}")

    # Results
    if "results" in st.session_state and st.session_state.results:
        res = st.session_state.results
        st.header("Results")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Summary")
            st.write(f"Total time : **{res['total_time']:.2f} min**")
            st.write(f"EXP / FOC : {p['nEXP']} / {p['nFOC']}")
            st.write(f"Capacity   : {p['capZone']} per zone")
        with c2:
            st.subheader("Export")
            csv = export_csv(res)
            st.download_button("Events CSV", csv["events"], f"events_{csv['ts']}.csv")
            st.download_button("Queue CSV", csv["queue"], f"queue_{csv['ts']}.csv")
            st.download_button("Zone CSV", csv["zone"], f"zone_{csv['ts']}.csv")

        tab1, tab2, tab3 = st.tabs(["Gantt", "Utilization", "Queue"])
        with tab1:
            fig = create_gantt_chart(res["events"])
            st.plotly_chart(fig, use_container_width=True) if fig else st.info("No data")
        with tab2:
            df_u = pd.DataFrame(
                [{"Time": s["time"], "Zone": f"Zone {z}", "Utilization": s["utilization"] * 100}
                 for z, lst in res["zone_stats"].items() for s in lst]
            )
            fig = create_line(df_u, "Time", "Utilization", color="Zone",
                              title="Zone Utilization", labels={"Utilization": "%"})
            st.plotly_chart(fig, use_container_width=True) if not df_u.empty else st.info("No data")
        with tab3:
            df_q = pd.DataFrame(res["queue_stats"])
            fig = create_line(df_q, "time", "queue_length",
                              title="Queue length", labels={"queue_length": "Riders"})
            st.plotly_chart(fig, use_container_width=True) if not df_q.empty else st.info("No data")
    else:
        st.info("Adjust parameters and click **Run simulation**.")


if __name__ == "__main__":
    main()
