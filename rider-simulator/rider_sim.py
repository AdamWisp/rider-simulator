import json
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import simpy
import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────── Simulation core ──────────────────────────── #
class RiderTrackSimulation:
    def __init__(self, params: dict):
        self.env = simpy.Environment()
        self.p = params.copy()

        # Zone resources
        self.zone_a = simpy.Resource(self.env, capacity=self.p['capZone'])
        self.zone_b = simpy.Resource(self.env, capacity=self.p['capZone'])
        self.zone_c = simpy.Resource(self.env, capacity=self.p['capZone'])

        # Stats
        self.events = []
        self.queue_stats = []
        self.util_stats = {'A': [], 'B': [], 'C': []}

        # Sync events
        self.inst_done = self.env.event()
        self.exp_done = self.env.event()
        if self.p['nEXP'] == 0:
            self.exp_done.succeed()

        # Completion barrier
        self.done_event = self.env.event()
        self.total_riders = 1 + self.p['nEXP'] + self.p['nFOC']
        self.finished = 0

        # Kick off instructor
        self.env.process(self.rider('INST-1', 'INST'))

    def record(self, rider_id, rider_type, zone, action):
        self.events.append({
            'rider_id': rider_id,
            'rider_type': rider_type,
            'zone': zone,
            'action': action,
            'time': self.env.now
        })

    def monitor_queue(self):
        while True:
            entered = sum(e['zone'] == 'Queue' and e['action'] == 'enter' for e in self.events)
            exited = sum(e['zone'] == 'Queue' and e['action'] == 'exit' for e in self.events)
            self.queue_stats.append({'time': self.env.now, 'queue_length': entered - exited})
            yield self.env.timeout(0.5)

    def monitor_util(self, tag, res):
        while True:
            self.util_stats[tag].append({'time': self.env.now, 'utilization': res.count / res.capacity})
            yield self.env.timeout(0.5)

    def rider(self, rid, rtype):
        # Queue
        self.record(rid, rtype, 'Queue', 'enter')

        # Gate into Zone A
        with self.zone_a.request() as req:
            yield req
            self.record(rid, rtype, 'Queue', 'exit')
            self.record(rid, rtype, 'Gate', 'enter')
            yield self.env.timeout(self.p['tEnter'])
            self.record(rid, rtype, 'Gate', 'exit')

        # Zone A
        self.record(rid, rtype, 'ZoneA', 'enter')
        yield self.env.timeout(self.p['tA'])
        self.record(rid, rtype, 'ZoneA', 'exit')

        # Zone B
        with self.zone_b.request() as req:
            yield req
            self.record(rid, rtype, 'ZoneB', 'enter')
            yield self.env.timeout(self.p['tB'])
            self.record(rid, rtype, 'ZoneB', 'exit')

        # Zone C
        with self.zone_c.request() as req:
            yield req
            self.record(rid, rtype, 'ZoneC', 'enter')
            yield self.env.timeout(self.p['tC'])
            self.record(rid, rtype, 'ZoneC', 'exit')

        # Exit Gate
        self.record(rid, rtype, 'Exit', 'enter')
        yield self.env.timeout(self.p['tExit'])
        self.record(rid, rtype, 'Exit', 'exit')

        # Trigger inst_done after full exit
        if rtype == 'INST' and not self.inst_done.triggered:
            self.inst_done.succeed()

        # Trigger exp_done after all EXP exit
        if rtype == 'EXP':
            done_exp = sum(1 for e in self.events if e['rider_type'] == 'EXP' and e['zone'] == 'Exit' and e['action'] == 'exit')
            if done_exp == self.p['nEXP'] and not self.exp_done.triggered:
                self.exp_done.succeed()

        # Completion
        self.finished += 1
        if self.finished == self.total_riders and not self.done_event.triggered:
            self.done_event.succeed()

    def inject_exp(self):
        yield self.inst_done
        for i in range(1, self.p['nEXP'] + 1):
            self.env.process(self.rider(f'EXP-{i}', 'EXP'))

    def inject_foc(self):
        yield self.exp_done
        for i in range(1, self.p['nFOC'] + 1):
            self.env.process(self.rider(f'FOC-{i}', 'FOC'))

    def run(self):
        self.env.process(self.monitor_queue())
        self.env.process(self.monitor_util('A', self.zone_a))
        self.env.process(self.monitor_util('B', self.zone_b))
        self.env.process(self.monitor_util('C', self.zone_c))
        self.env.process(self.inject_exp())
        self.env.process(self.inject_foc())
        self.env.run(until=self.done_event)
        total_time = max(e['time'] for e in self.events) if self.events else 0
        return {'events': self.events, 'queue': self.queue_stats, 'util': self.util_stats, 'total_time': total_time}

# ─────────────────────────── Streamlit UI ──────────────────────────── #
def main():
    st.set_page_config(page_title='Rider Simulator', layout='wide')
    st.title('🏍️ Rider Training Track')

    defaults = {'nEXP':25,'nFOC':10,'capZone':1,'tEnter':0.5,'tA':5.0,'tB':5.0,'tC':5.0,'tExit':0.5}
    if 'params' not in st.session_state:
        st.session_state.params = defaults.copy()
    p = st.session_state.params

    st.sidebar.header('Parameters')
    p['nEXP']    = st.sidebar.number_input('EXP riders', 0,100,p['nEXP'])
    p['nFOC']    = st.sidebar.number_input('FOC riders', 0,100,p['nFOC'])
    p['capZone'] = st.sidebar.number_input('Riders/zone',1,6,p['capZone'])

    st.sidebar.subheader('Times (min)')
    for key, lo, hi in [
        ('tEnter', 0.0, 5.0),
        ('tA',      1.0, 20.0),
        ('tB',      1.0, 20.0),
        ('tC',      1.0, 20.0),
        ('tExit',   0.0, 5.0),
    ]:
        p[key] = st.sidebar.number_input(
            label=key,
            min_value=lo,
            max_value=hi,
            value=p[key],
            step=0.1 if key in ['tEnter','tExit'] else 0.5
        )

    if st.sidebar.button('Run Simulation'):
        st.session_state.res = RiderTrackSimulation(p).run()
        st.session_state.animate=False

    if 'res' in st.session_state:
        res = st.session_state.res
        st.subheader(f"Total: {res['total_time']:.2f} min")
        inst = max(e['time'] for e in res['events'] if e['rider_id']=='INST-1' and e['zone']=='Exit')
        exp  = max((e['time'] for e in res['events'] if e['rider_type']=='EXP' and e['zone']=='Exit'), default=0)
        foc  = max((e['time'] for e in res['events'] if e['rider_type']=='FOC' and e['zone']=='Exit'), default=0)
        st.write(f"Instructor: {inst:.2f}, EXP: {exp:.2f}, FOC: {foc:.2f}")

        # HTML5 Canvas animation
        events_json = json.dumps(res['events'])
        html = f"""
<canvas id='trackCanvas' width='800' height='200'></canvas>
<script>
const events = {events_json};
const zones = ['Queue','Gate','ZoneA','ZoneB','ZoneC','Exit'];
let t=0;
const dt = 0.1;
const canvas = document.getElementById('trackCanvas');
const ctx = canvas.getContext('2d');
const ypos = {{Queue:20,Gate:60,ZoneA:100,ZoneB:140,ZoneC:180,Exit:220}};
function draw() {{
  ctx.clearRect(0,0,800,200);
  ctx.font='12px sans-serif';
  events.forEach(e=>{{
    if(e.time<=t && e.time+dt>t){{
      const x = (t/Math.max(...events.map(ev=>ev.time)))*800;
      const y = ypos[e.zone]||ypos['Queue'];
      ctx.fillText(e.rider_id[0],x,y);
    }}
  }});
  t+=dt;
  if(t<Math.max(...events.map(e=>e.time))) requestAnimationFrame(draw);
}}
draw();
</script>
"""
        components.html(html,height=250)

if __name__=='__main__':
    main()
