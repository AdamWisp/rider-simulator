import json
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ────────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Simulator", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar Inputs ---
    st.sidebar.header("Batch Sizes")
    n_exp = st.sidebar.number_input("Number of EXP Riders", min_value=0, max_value=100,
                                     value=25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", min_value=0, max_value=100,
                                     value=10, key="n_foc")

    st.sidebar.header("Instructor Zone Times (min)")
    inst_a = st.sidebar.number_input("Instructor Zone A", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_a")
    inst_b = st.sidebar.number_input("Instructor Zone B", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_b")
    inst_c = st.sidebar.number_input("Instructor Zone C", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_c")

    st.sidebar.header("EXP Zone Times (min)")
    exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_a")
    exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_b")
    exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_c")

    st.sidebar.header("FOC Zone Times (min)")
    foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_a")
    foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_b")
    foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_c")

    # Run simulation button
    if st.sidebar.button("Start Simulation", key="start_sim"):
        # Build rider schedule sequentially
        riders = []
        current_time = 0.0

        # Instructor
        riders.append({
            "id": "INST-1",
            "start": current_time,
            "a": inst_a,
            "b": inst_b,
            "c": inst_c
        })
        current_time += inst_a + inst_b + inst_c

        # EXP riders sequentially
        for i in range(1, n_exp + 1):
            riders.append({
                "id": f"EXP-{i}",
                "start": current_time,
                "a": exp_a,
                "b": exp_b,
                "c": exp_c
            })
            current_time += exp_a + exp_b + exp_c

        # FOC riders sequentially
        for i in range(1, n_foc + 1):
            riders.append({
                "id": f"FOC-{i}",
                "start": current_time,
                "a": foc_a,
                "b": foc_b,
                "c": foc_c
            })
            current_time += foc_a + foc_b + foc_c

        total_time = current_time

        # Display summary
        st.subheader("Simulation Results")
        st.write(f"Total Elapsed Time: **{total_time:.2f} minutes**")
        if riders:
            inst_finish = riders[0]['start'] + riders[0]['a'] + riders[0]['b'] + riders[0]['c']
            st.write(f"Instructor finished at: {inst_finish:.2f} min")
        if n_exp:
            exp_finish = riders[n_exp]['start'] + riders[n_exp]['a'] + riders[n_exp]['b'] + riders[n_exp]['c']
            st.write(f"EXP batch finished at: {exp_finish:.2f} min")
        if n_foc:
            foc_finish = riders[-1]['start'] + riders[-1]['a'] + riders[-1]['b'] + riders[-1]['c']
            st.write(f"FOC batch finished at: {foc_finish:.2f} min")

        # Pass data to JS for animation & timer
        riders_json = json.dumps(riders)
        html = f"""
<div style='font:16px monospace;' id='timer'>Time: 0.00 min</div>
<canvas id='trackCanvas' width='900' height='240'></canvas>
<script>
const riders = {riders_json};
const totalTime = {total_time};
const dt = 0.05;
const canvas = document.getElementById('trackCanvas');
const ctx = canvas.getContext('2d');
const timerDiv = document.getElementById('timer');

// Regions: Queue, A, B, C, Exit
const regions = [
  {{name:'Queue', x0:20,  width:80}},
  {{name:'A',     x0:120, width:200}},
  {{name:'B',     x0:340, width:200}},
  {{name:'C',     x0:560, width:200}},
  {{name:'Exit',  x0:780, width:80}}
];
const yPos = {{INST:60, EXP:140, FOC:220}};

let t = 0;
function draw() {{
  ctx.clearRect(0, 0, 900, 240);
  // draw regions
  ctx.font = '14px sans-serif';
  regions.forEach(r => {{
    ctx.fillText(r.name, r.x0+10, 30);
    ctx.strokeRect(r.x0, 40, r.width, 180);
  }});

  // update timer
  timerDiv.innerText = `Time: ${t.toFixed(2)} min`;

  riders.forEach(r => {{
    if(t < r.start) return;
    let elapsed = t - r.start;
    let x, y = yPos[r.id.split('-')[0]];
    if(elapsed < r.a) {{
      x = regions[1].x0 + (elapsed/r.a)*regions[1].width;
    }} else if(elapsed < r.a + r.b) {{
      elapsed -= r.a;
      x = regions[2].x0 + (elapsed/r.b)*regions[2].width;
    }} else if(elapsed < r.a + r.b + r.c) {{
      elapsed -= (r.a + r.b);
      x = regions[3].x0 + (elapsed/r.c)*regions[3].width;
    }} else {{
      x = regions[4].x0 + regions[4].width;
    }}
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, 2*Math.PI);
    ctx.fillStyle = r.id.startsWith('INST') ? '#ff0000' : r.id.startsWith('EXP') ? '#00aa00' : '#0000ff';
    ctx.fill();
    ctx.fillStyle = '#000';
    ctx.fillText(r.id.split('-')[0], x-5, y+25);
  }});

  t += dt;
  if(t < totalTime + 1) requestAnimationFrame(draw);
}}
draw();
</script>
"""
        components.html(html, height=300)

if __name__ == '__main__':
    main()
