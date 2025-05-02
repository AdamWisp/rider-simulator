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
    n_exp = st.sidebar.number_input("Number of EXP Riders", min_value=0, max_value=100, value=25)
    n_foc = st.sidebar.number_input("Number of FOC Riders", min_value=0, max_value=100, value=10)

    st.sidebar.header("Instructor Times (min)")
    inst_zone = st.sidebar.number_input("Zone Training", 0.0, 60.0, 5.0, 0.1)
    inst_practice = st.sidebar.number_input("Area Practice", 0.0, 60.0, 3.0, 0.1)
    inst_test = st.sidebar.number_input("Test", 0.0, 60.0, 2.0, 0.1)

    st.sidebar.header("EXP Times (min)")
    exp_zone = st.sidebar.number_input("Zone Training", 0.0, 60.0, 4.0, 0.1)
    exp_practice = st.sidebar.number_input("Area Practice", 0.0, 60.0, 2.0, 0.1)
    exp_test = st.sidebar.number_input("Test", 0.0, 60.0, 1.5, 0.1)

    st.sidebar.header("FOC Times (min)")
    foc_zone = st.sidebar.number_input("Zone Training", 0.0, 60.0, 3.0, 0.1)
    foc_practice = st.sidebar.number_input("Area Practice", 0.0, 60.0, 2.5, 0.1)
    foc_test = st.sidebar.number_input("Test", 0.0, 60.0, 2.0, 0.1)

    # Run simulation button
    if st.sidebar.button("Start Simulation"):
        # Build rider schedule sequentially
        riders = []
        current_time = 0.0

        # Instructor
        riders.append({
            "id": "INST-1",
            "start": current_time,
            "zone": inst_zone,
            "practice": inst_practice,
            "test": inst_test
        })
        current_time += inst_zone + inst_practice + inst_test

        # EXP riders sequentially
        for i in range(1, n_exp + 1):
            riders.append({
                "id": f"EXP-{i}",
                "start": current_time,
                "zone": exp_zone,
                "practice": exp_practice,
                "test": exp_test
            })
            current_time += exp_zone + exp_practice + exp_test

        # FOC riders sequentially
        for i in range(1, n_foc + 1):
            riders.append({
                "id": f"FOC-{i}",
                "start": current_time,
                "zone": foc_zone,
                "practice": foc_practice,
                "test": foc_test
            })
            current_time += foc_zone + foc_practice + foc_test

        total_time = current_time

        # Display summary
        st.subheader("Simulation Results")
        st.write(f"Total Elapsed Time: **{total_time:.2f} minutes**")
        if riders:
            inst_finish = riders[0]['start'] + riders[0]['zone'] + riders[0]['practice'] + riders[0]['test']
            st.write(f"Instructor finished at: {inst_finish:.2f} min")
        if n_exp:
            exp_finish = riders[n_exp]['start'] + riders[n_exp]['zone'] + riders[n_exp]['practice'] + riders[n_exp]['test']
            st.write(f"EXP batch finished at: {exp_finish:.2f} min")
        if n_foc:
            foc_finish = riders[-1]['start'] + riders[-1]['zone'] + riders[-1]['practice'] + riders[-1]['test']
            st.write(f"FOC batch finished at: {foc_finish:.2f} min")

        # Pass data to JS for animation
        riders_json = json.dumps(riders)
        html = f"""
<canvas id='trackCanvas' width='900' height='200'></canvas>
<script>
const riders = {riders_json};
const totalTime = {total_time};
const dt = 0.05;
const canvas = document.getElementById('trackCanvas');
const ctx = canvas.getContext('2d');

// Region definitions (pixels)
const regions = [
  {{name:'Queue', x0: 20, width: 80}},
  {{name:'Zone', x0:120, width:200}},
  {{name:'Practice', x0:340, width:200}},
  {{name:'Test', x0:560, width:200}},
  {{name:'Exit', x0:780, width:80}}
];
// Y positions by group
const yPos = {{INST:50, EXP:120, FOC:190}};

let t = 0;
function draw() {{
  ctx.clearRect(0,0,900,200);
  // draw region labels
  ctx.font = '14px sans-serif';
  regions.forEach(r => {{
    ctx.fillText(r.name, r.x0+10, 20);
    ctx.strokeRect(r.x0, 30, r.width, 140);
  }});

  riders.forEach((r,index) => {{
    const start = r.start;
    let x, y;
    if(t < start) return; // not started
    const elapsed = t - start;
    // determine stage
    if(elapsed < r.zone) {{
      // in zone
      const f = elapsed/r.zone;
      x = regions[1].x0 + f*regions[1].width;
      y = yPos[r.id.split('-')[0]];
    }} else if(elapsed < r.zone + r.practice) {{
      // in practice
      const f = (elapsed - r.zone)/r.practice;
      x = regions[2].x0 + f*regions[2].width;
      y = yPos[r.id.split('-')[0]];
    }} else if(elapsed < r.zone + r.practice + r.test) {{
      // in test
      const f = (elapsed - r.zone - r.practice)/r.test;
      x = regions[3].x0 + f*regions[3].width;
      y = yPos[r.id.split('-')[0]];
    }} else {{
      // finished, in exit region
      const f = Math.min((elapsed - r.zone - r.practice - r.test)/1,1);
      x = regions[4].x0 + f*regions[4].width;
      y = yPos[r.id.split('-')[0]];
    }}
    // draw rider icon
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, 2*Math.PI);
    if(r.id.startsWith('INST')) ctx.fillStyle='#ff0000';
    else if(r.id.startsWith('EXP')) ctx.fillStyle='#00aa00';
    else ctx.fillStyle='#0000ff';
    ctx.fill();
    ctx.fillStyle='#000';
    ctx.fillText(r.id.split('-')[0], x-5, y+25);
  }});

  t += dt;
  if(t < totalTime + 1) requestAnimationFrame(draw);
}}
draw();
</script>
"""
        components.html(html, height=240)

if __name__ == '__main__':
    main()
