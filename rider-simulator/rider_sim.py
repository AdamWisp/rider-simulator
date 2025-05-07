import json
import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ───────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Track Simulation", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar: Configuration ---
    st.sidebar.header("Batch & Capacity")
    n_exp = st.sidebar.number_input("Number of EXP Riders", 0, 100, 25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", 0, 100, 10, key="n_foc")
    cap_zone = st.sidebar.number_input("Riders per Zone", 1, 2, 1, key="cap_zone")

    # --- Sidebar: Per-Zone Durations ---
    st.sidebar.header("Zone-by-Zone Durations (minutes)")
    st.sidebar.subheader("Instructor Zone Times")
    inst_a = st.sidebar.number_input("Inst Zone A", 0.0, 180.0, 5.0, 0.1, key="inst_a")
    inst_b = st.sidebar.number_input("Inst Zone B", 0.0, 180.0, 5.0, 0.1, key="inst_b")
    inst_c = st.sidebar.number_input("Inst Zone C", 0.0, 180.0, 5.0, 0.1, key="inst_c")
    st.sidebar.subheader("EXP Zone Times")
    exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 180.0, 4.0, 0.1, key="exp_a")
    exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 180.0, 4.0, 0.1, key="exp_b")
    exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 180.0, 4.0, 0.1, key="exp_c")
    st.sidebar.subheader("FOC Zone Times")
    foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 180.0, 3.0, 0.1, key="foc_a")
    foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 180.0, 3.0, 0.1, key="foc_b")
    foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 180.0, 3.0, 0.1, key="foc_c")

    # --- Sidebar: Other Phases ---
    st.sidebar.header("Other Phases (one-time)")
    inst_lap = st.sidebar.number_input("Instructor Whole Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
    exp_lap = st.sidebar.number_input("EXP Whole Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
    foc_lap = st.sidebar.number_input("FOC Whole Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")
    inst_test = st.sidebar.number_input("Instructor Test", 0.0, 180.0, 5.0, 0.1, key="inst_test")
    exp_test = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="exp_test")
    foc_test = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="foc_test")

    # --- Sidebar: Select Phases for EXP/FOC ---
    st.sidebar.header("Select EXP/FOC Phases")
    phases_selected = st.sidebar.multiselect(
        "Include phases:", ["Per-Zone", "Whole Lap", "Test"],
        default=["Per-Zone", "Whole Lap", "Test"], key="phases"
    )
    phase_order = ["Per-Zone", "Whole Lap", "Test"]
    phases = [p for p in phase_order if p in phases_selected]

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation"):
        exit_time = 0.5
        schedule = []
        phase_times = []
        phase_labels = []
        current = 0.0

        def pipeline(start, count, a, b, c, cap, label):
            A_free = [start]*cap
            B_free = [start]*cap
            C_free = [start]*cap
            out = []
            for i in range(count):
                rid = f"{label}{i+1 if label!='INST' else ''}"
                ia = min(range(cap), key=lambda idx: A_free[idx])
                ta = A_free[ia]; A_free[ia] = ta + a
                tb_ready = ta + a
                ib = min(range(cap), key=lambda idx: max(B_free[idx], tb_ready))
                tb = max(B_free[ib], tb_ready); B_free[ib] = tb + b
                tc_ready = tb + b
                ic = min(range(cap), key=lambda idx: max(C_free[idx], tc_ready))
                tc = max(C_free[ic], tc_ready); C_free[ic] = tc + c
                te = tc + c; tf = te + exit_time
                out.append({"id": rid, "start": ta, "a": a, "b": b, "c": c, "exit": te, "finish": tf})
            return out

        # 1) Instructor does zones then lap then test
        # Zones
        inst_zone = pipeline(0.0, 1, inst_a, inst_b, inst_c, 1, 'INST')
        schedule += inst_zone
        current = inst_zone[0]['finish']
        phase_times.append(current)
        phase_labels.append({'batch':'INST','phase':'Per-Zone'})
        # Whole lap
        inst_l = pipeline(current, 1, inst_lap/3, inst_lap/3, inst_lap/3, 1, 'INST')
        schedule += inst_l; current = inst_l[0]['finish']
        phase_times.append(current)
        phase_labels.append({'batch':'INST','phase':'Whole Lap'})
        # Test
        inst_t = pipeline(current, 1, inst_test/3, inst_test/3, inst_test/3, 1, 'INST')
        schedule += inst_t; current = inst_t[0]['finish']
        phase_times.append(current)
        phase_labels.append({'batch':'INST','phase':'Test'})

        # 2) EXP
        for ph in phases:
            if ph=='Per-Zone': params=(exp_a, exp_b, exp_c, cap_zone)
            elif ph=='Whole Lap': params=(exp_lap/3, exp_lap/3, exp_lap/3, 1)
            else: params=(exp_test/3, exp_test/3, exp_test/3, 1)
            out = pipeline(current, n_exp, *params, 'EXP')
            schedule += out
            if out: current = out[-1]['finish']
            phase_times.append(current)
            phase_labels.append({'batch':'EXP','phase':ph})

        # 3) FOC
        for ph in phases:
            if ph=='Per-Zone': params=(foc_a, foc_b, foc_c, cap_zone)
            elif ph=='Whole Lap': params=(foc_lap/3, foc_lap/3, foc_lap/3, 1)
            else: params=(foc_test/3, foc_test/3, foc_test/3, 1)
            out = pipeline(current, n_foc, *params, 'FOC')
            schedule += out
            if out: current = out[-1]['finish']
            phase_times.append(current)
            phase_labels.append({'batch':'FOC','phase':ph})

        total_time = current

        st.subheader("Simulation Results")
        st.write(f"Total elapsed time: **{total_time:.2f}** minutes")

        riders_data = json.dumps(schedule)
        seq_data = json.dumps(phase_labels)
        time_data = json.dumps(phase_times)
        html = f"""
<div style='display:flex; gap:20px; font:16px monospace;'>
  <div id='timer'>Time: 0.00 min</div>
  <div id='indicator'>Phase: INST - Per-Zone</div>
</div>
<canvas id='track' width='900' height='360'></canvas>
<script>
const riders = {riders_data};
const seq = {seq_data};
const pts = {time_data};
const total = {total_time};
const dt = 0.05, exitTime = {exit_time};
const ctx = document.getElementById('track').getContext('2d');
const timerDiv = document.getElementById('timer');
const indDiv = document.getElementById('indicator');
const regs = [
  {{ x: 20, w: 60, n: 'Queue' }},
  {{ x: 120, w: 200, n: 'A' }},
  {{ x: 340, w: 200, n: 'B' }},
  {{ x: 560, w: 200, n: 'C' }},
  {{ x: 780, w: 80, n: 'Exit' }}
];
const ypos = {{ 'INST': 80, 'EXP': 160, 'FOC': 240 }};
let t = 0;
function draw() {{
  ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif';
  regs.forEach(r=>{{ctx.strokeRect(r.x,40,r.w,260);ctx.fillText(r.n,r.x+5,30);}});
  timerDiv.innerText = `Time: ${{t.toFixed(2)}} min`;
  for(let i=0;i<pts.length;i++){{ if(t<pts[i]){{ indDiv.innerText = `Phase: ${{seq[i].batch}} - ${{seq[i].phase}}`; break; }} }}
  riders.forEach(r=>{{ if(t<r.start) return; let e=t-r.start; let x; if(e<r.a) x=regs[1].x+e/r.a*regs[1].w; else if(e<r.a+r.b){{ e-=r.a; x=regs[2].x+e/r.b*regs[2].w; }} else if(e<r.a+r.b+r.c){{ e-=(r.a+r.b); x=regs[3].x+e/r.c*regs[3].w; }} else if(e<r.a+r.b+r.c+exitTime){{ e-=(r.a+r.b+r.c); x=regs[4].x+e/exitTime*regs[4].w; }} else x=regs[0].x+regs[0].w/2; let y=ypos[r.id.replace(/[0-9]/g,'')]; ctx.beginPath(); ctx.fillStyle=r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,y,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id,x-10,y+20); }});
  t+=dt; if(t<total+exitTime) requestAnimationFrame(draw);
}}
requestAnimationFrame(draw);
</script>
"""
        components.html(html, height=480)

if __name__=='__main__':
    main()
