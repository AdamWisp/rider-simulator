import simpy
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.figure_factory as ff
import time
from datetime import datetime

class RiderTrackSimulation:
    def __init__(self, params):
        self.env = simpy.Environment()
        self.params = params
        
        # Create resources (zones)
        self.zone_a = simpy.Resource(self.env, capacity=params['capZone'])
        self.zone_b = simpy.Resource(self.env, capacity=params['capZone'])
        self.zone_c = simpy.Resource(self.env, capacity=params['capZone'])
        
        # Stats tracking
        self.rider_events = []
        self.queue_stats = []
        self.zone_stats = {'A': [], 'B': [], 'C': []}
        self.riders_in_queue = 0
        
        # Timing tracking
        self.last_exp_exit_time = 0
        self.total_sim_time = 0
        
        # Inject the instructor first
        self.env.process(self.rider_process("INST-1", "INST"))
        
    def record_event(self, rider_id, rider_type, zone, action, time):
        """Record rider events for visualization"""
        self.rider_events.append({
            'rider_id': rider_id,
            'rider_type': rider_type,
            'zone': zone,
            'action': action,
            'time': time
        })
    
    def track_queue(self):
        """Record queue length over time"""
        max_time = 1000  # Same as simulation timeout
        current_time = 0
        
        while current_time < max_time:
            self.queue_stats.append({
                'time': self.env.now,
                'queue_length': self.riders_in_queue
            })
            yield self.env.timeout(0.5)  # Sample every half minute
            current_time += 0.5
    
    def track_zone_utilization(self, zone, resource):
        """Track zone utilization stats"""
        max_time = 1000  # Same as simulation timeout
        current_time = 0
        
        while current_time < max_time:
            self.zone_stats[zone].append({
                'time': self.env.now,
                'utilization': resource.count / resource.capacity
            })
            yield self.env.timeout(0.5)  # Sample every half minute
            current_time += 0.5
        
    def rider_process(self, rider_id, rider_type):
        """Process for a single rider going through the track"""
        # Enter queue
        arrival_time = self.env.now
        self.riders_in_queue += 1
        self.record_event(rider_id, rider_type, "Queue", "enter", self.env.now)
        
        # Process for Zone A
        with self.zone_a.request() as request:
            # Wait until there's space in Zone A
            yield request
            
            # Enter gate - leaving queue and entering track
            self.riders_in_queue -= 1
            self.record_event(rider_id, rider_type, "Queue", "exit", self.env.now)
            self.record_event(rider_id, rider_type, "EnterGate", "enter", self.env.now)
            yield self.env.timeout(self.params['tEnter'])
            self.record_event(rider_id, rider_type, "EnterGate", "exit", self.env.now)
            
            if rider_type == "INST":
                self.inst_exit_time = self.env.now
            elif rider_type == "EXP":
                self.last_exp_exit_time = self.env.now
            
            # Zone A
            self.record_event(rider_id, rider_type, "ZoneA", "enter", self.env.now)
            yield self.env.timeout(self.params['tA'])
            self.record_event(rider_id, rider_type, "ZoneA", "exit", self.env.now)
        
        # Process for Zone B
        with self.zone_b.request() as request:
            yield request
            self.record_event(rider_id, rider_type, "ZoneB", "enter", self.env.now)
            yield self.env.timeout(self.params['tB'])
            self.record_event(rider_id, rider_type, "ZoneB", "exit", self.env.now)
        
        # Process for Zone C
        with self.zone_c.request() as request:
            yield request
            self.record_event(rider_id, rider_type, "ZoneC", "enter", self.env.now)
            yield self.env.timeout(self.params['tC'])
            self.record_event(rider_id, rider_type, "ZoneC", "exit", self.env.now)
        
        # Exit gate
        self.record_event(rider_id, rider_type, "ExitGate", "enter", self.env.now)
        yield self.env.timeout(self.params['tExit'])
        self.record_event(rider_id, rider_type, "ExitGate", "exit", self.env.now)
        
        # Record total time for this rider
        total_time = self.env.now - arrival_time
        
    def inject_exp_riders(self):
        """Inject experienced riders after instructor exits"""
        # Initialize inst_exit_time in case it's not set yet
        if not hasattr(self, 'inst_exit_time'):
            self.inst_exit_time = 0
            
        yield self.env.timeout(self.inst_exit_time)  # Wait for instructor to exit entry gate
        
        # Schedule all EXP riders
        for i in range(1, self.params['nEXP'] + 1):
            self.env.process(self.rider_process(f"EXP-{i}", "EXP"))
    
    def inject_foc_riders(self):
        """Inject focus riders after all EXP riders exit"""
        # Initialize last_exp_exit_time in case it's not set yet
        if not hasattr(self, 'last_exp_exit_time'):
            # If nEXP is 0, we'll never set last_exp_exit_time
            if self.params['nEXP'] == 0:
                # Use instructor exit time instead
                self.last_exp_exit_time = getattr(self, 'inst_exit_time', 0)
            else:
                self.last_exp_exit_time = 0
                
        yield self.env.timeout(self.last_exp_exit_time)  # Wait for last EXP rider to exit entry gate
        
        # Schedule all FOC riders
        for i in range(1, self.params['nFOC'] + 1):
            self.env.process(self.rider_process(f"FOC-{i}", "FOC"))
    
    def run(self):
        """Run the simulation"""
        # Start queue length tracking
        self.env.process(self.track_queue())
        
        # Start zone utilization tracking
        self.env.process(self.track_zone_utilization('A', self.zone_a))
        self.env.process(self.track_zone_utilization('B', self.zone_b))
        self.env.process(self.track_zone_utilization('C', self.zone_c))
        
        # Schedule EXP and FOC rider injections
        self.env.process(self.inject_exp_riders())
        self.env.process(self.inject_foc_riders())
        
        # Run the simulation with a timeout to prevent infinite execution
        # This ensures the simulation will end even if there's a logical issue
        max_simulation_time = 1000  # Set a reasonable upper bound in minutes
        try:
            self.env.run(until=max_simulation_time)
        except Exception as e:
            print(f"Simulation stopped with error: {e}")
            # Continue to return results anyway
        
        # Calculate total simulation time based on the last exit event
        if self.rider_events:
            self.total_sim_time = max(event['time'] for event in self.rider_events)
        else:
            self.total_sim_time = 0
        
        return {
            'events': self.rider_events,
            'queue_stats': self.queue_stats,
            'zone_stats': self.zone_stats,
            'total_time': self.total_sim_time
        }

def create_gantt_chart(events):
    """Create a Gantt chart from simulation events"""
    df = pd.DataFrame(events)
    
    # Process events into tasks for gantt chart
    tasks = []
    
    # Group by rider and zone to find start/finish times
    for rider_id in df['rider_id'].unique():
        rider_data = df[df['rider_id'] == rider_id]
        rider_type = rider_data['rider_type'].iloc[0]
        
        for zone in ['Queue', 'EnterGate', 'ZoneA', 'ZoneB', 'ZoneC', 'ExitGate']:
            zone_data = rider_data[rider_data['zone'] == zone]
            
            if len(zone_data) >= 2:  # We need at least enter and exit events
                enter_events = zone_data[zone_data['action'] == 'enter']
                exit_events = zone_data[zone_data['action'] == 'exit']
                
                for i in range(min(len(enter_events), len(exit_events))):
                    start_time = enter_events.iloc[i]['time']
                    finish_time = exit_events.iloc[i]['time']
                    
                    tasks.append({
                        'Task': rider_id,
                        'Start': start_time,
                        'Finish': finish_time,
                        'Resource': zone,
                        'Type': rider_type
                    })
    
    # Convert to DataFrame for plotting
    tasks_df = pd.DataFrame(tasks)
    
    if not tasks_df.empty:
        # Sort by resource and start time
        tasks_df = tasks_df.sort_values(by=['Type', 'Task', 'Start'])
        
        # Create color mapping
        colors = {'INST': 'rgb(255, 0, 0)', 'EXP': 'rgb(0, 255, 0)', 'FOC': 'rgb(0, 0, 255)'}
        
        # Create the Gantt chart
        fig = ff.create_gantt(
            tasks_df, 
            colors=colors,
            index_col='Resource',
            group_tasks=True,
            show_colorbar=True,
            title='Rider Training Track Simulation',
        )
        
        # Update layout
        fig.update_layout(
            xaxis_title='Time (minutes)',
            yaxis_title='Rider',
            legend_title='Rider Type',
            height=600,
        )
        
        return fig
    else:
        return None

def create_zone_utilization_chart(zone_stats):
    """Create zone utilization chart"""
    # Combine zone stats
    all_stats = []
    for zone, stats in zone_stats.items():
        for stat in stats:
            all_stats.append({
                'Time': stat['time'],
                'Zone': f'Zone {zone}',
                'Utilization': stat['utilization'] * 100  # Convert to percentage
            })
    
    df = pd.DataFrame(all_stats)
    
    if not df.empty:
        fig = px.line(
            df, 
            x='Time', 
            y='Utilization', 
            color='Zone',
            title='Zone Utilization Over Time',
            labels={'Utilization': 'Utilization (%)'},
        )
        
        fig.update_layout(
            xaxis_title='Time (minutes)',
            yaxis_title='Utilization (%)',
            yaxis_range=[0, 100],
        )
        
        return fig
    else:
        return None

def create_queue_length_chart(queue_stats):
    """Create queue length chart"""
    df = pd.DataFrame(queue_stats)
    
    if not df.empty:
        fig = px.line(
            df,
            x='time',
            y='queue_length',
            title='Queue Length Over Time',
        )
        
        fig.update_layout(
            xaxis_title='Time (minutes)',
            yaxis_title='Number of Riders in Queue',
        )
        
        return fig
    else:
        return None

def create_animation_frame(events, current_time, params):
    """Create a frame for the animation at a specific time"""
    # Find all riders who have entered but not exited each zone at current_time
    zones = ['Queue', 'EnterGate', 'ZoneA', 'ZoneB', 'ZoneC', 'ExitGate']
    
    # Check if events is empty
    if not events:
        st.write("No simulation data available for animation.")
        return
    
    # Create a DataFrame from events
    df = pd.DataFrame(events)
    
    # Initialize zone occupancy
    zone_occupancy = {zone: [] for zone in zones}
    
    # Group events by rider
    for rider_id in df['rider_id'].unique():
        rider_data = df[df['rider_id'] == rider_id]
        
        # Find the current zone for this rider at current_time
        current_zone = None
        
        for zone in zones:
            # Skip if no data for this zone
            if zone not in rider_data['zone'].values:
                continue
                
            zone_data = rider_data[rider_data['zone'] == zone]
            enters = zone_data[zone_data['action'] == 'enter']
            exits = zone_data[zone_data['action'] == 'exit']
            
            # Skip if no enter events
            if enters.empty:
                continue
                
            # Check if rider is in this zone at current_time
            for enter_idx, enter_row in enters.iterrows():
                enter_time = enter_row['time']
                
                # Find matching exit or use current_time if none
                exit_times = exits[exits['time'] > enter_time]['time'].tolist()
                exit_time = min(exit_times) if exit_times else float('inf')
                
                if enter_time <= current_time < exit_time:
                    current_zone = zone
                    zone_occupancy[zone].append(rider_id)
                    break
            
            if current_zone:
                break
    
    # Create a visualization
    st.write(f"Simulation Time: {current_time:.2f} minutes")
    
    # Draw track layout
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.write("## Queue")
        for rider in zone_occupancy['Queue']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
    
    with col2:
        st.write("## Gate")
        for rider in zone_occupancy['EnterGate']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
    
    with col3:
        st.write("## Zone A")
        st.write(f"(Slow Riding: {params['tA']} min)")
        for rider in zone_occupancy['ZoneA']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
    
    with col4:
        st.write("## Zone B")
        st.write(f"(Decision Making: {params['tB']} min)")
        for rider in zone_occupancy['ZoneB']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
    
    with col5:
        st.write("## Zone C")
        st.write(f"(Obstacle: {params['tC']} min)")
        for rider in zone_occupancy['ZoneC']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
    
    with col6:
        st.write("## Exit")
        for rider in zone_occupancy['ExitGate']:
            # Check if rider exists in DataFrame
            if rider in df['rider_id'].values:
                rider_data = df[df['rider_id'] == rider]
                if not rider_data.empty and 'rider_type' in rider_data.columns:
                    rider_type = rider_data['rider_type'].iloc[0]
                    if rider_type == "INST":
                        st.write(f"🔴 {rider}")
                    elif rider_type == "EXP":
                        st.write(f"🟢 {rider}")
                    else:  # FOC
                        st.write(f"🔵 {rider}")
                        
    # Legend
    st.write("---")
    st.write("🔴 INST: Instructor | 🟢 EXP: Experienced Riders | 🔵 FOC: Focus Riders")

def export_to_csv(results):
    """Export simulation results to CSV"""
    # Create events dataframe
    events_df = pd.DataFrame(results['events'])
    
    # Create other stat dataframes
    queue_df = pd.DataFrame(results['queue_stats'])
    
    zone_stats = []
    for zone, stats in results['zone_stats'].items():
        for stat in stats:
            stat_copy = stat.copy()
            stat_copy['zone'] = zone
            zone_stats.append(stat_copy)
    zone_stats_df = pd.DataFrame(zone_stats)
    
    # Format timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create CSV strings
    events_csv = events_df.to_csv(index=False)
    queue_csv = queue_df.to_csv(index=False)
    zone_stats_csv = zone_stats_df.to_csv(index=False)
    
    return {
        'events': events_csv,
        'queue_stats': queue_csv,
        'zone_stats': zone_stats_csv,
        'timestamp': timestamp
    }

def run_simulation(params):
    """Run simulation with given parameters"""
    simulation = RiderTrackSimulation(params)
    results = simulation.run()
    return results

def save_scenario(params):
    """Save scenario parameters as JSON"""
    return params

def main():
    try:
        st.set_page_config(
            page_title="Rider Training Track Simulation",
            page_icon="🏍️",
            layout="wide",
        )
    except Exception:
        # Page config may have already been set
        pass
    
    st.title("🏍️ Rider Training Track Simulation")
    
    # Sidebar for inputs
    st.sidebar.header("Simulation Parameters")
    
    # Initialize session state for parameters
    if 'params' not in st.session_state:
        st.session_state.params = {
            'nEXP': 25,
            'nFOC': 10,
            'capZone': 1,
            'tEnter': 0.5,
            'tA': 5.0,
            'tB': 5.0,
            'tC': 5.0,
            'tExit': 0.5
        }
    
    # Initialize session state for results
    if 'results' not in st.session_state:
        st.session_state.results = None
    
    # Initialize session state for animation
    if 'animate' not in st.session_state:
        st.session_state.animate = False
    
    # Input parameters
    st.session_state.params['nEXP'] = st.sidebar.number_input("Number of EXP Riders", 1, 100, value=st.session_state.params['nEXP'])
    st.session_state.params['nFOC'] = st.sidebar.number_input("Number of FOC Riders", 0, 100, value=st.session_state.params['nFOC'])
    st.session_state.params['capZone'] = st.sidebar.number_input("Riders per Zone", 1, 6, value=st.session_state.params['capZone'])
    
    st.sidebar.subheader("Time Parameters (minutes)")
    st.session_state.params['tEnter'] = st.sidebar.number_input("Time to Enter Track", 0.0, 5.0, value=st.session_state.params['tEnter'], step=0.1)
    st.session_state.params['tA'] = st.sidebar.number_input("Zone A Dwell Time", 1.0, 20.0, value=st.session_state.params['tA'], step=0.5)
    st.session_state.params['tB'] = st.sidebar.number_input("Zone B Dwell Time", 1.0, 20.0, value=st.session_state.params['tB'], step=0.5)
    st.session_state.params['tC'] = st.sidebar.number_input("Zone C Dwell Time", 1.0, 20.0, value=st.session_state.params['tC'], step=0.5)
    st.session_state.params['tExit'] = st.sidebar.number_input("Exit & Re-queue Time", 0.0, 5.0, value=st.session_state.params['tExit'], step=0.1)
    
    # Button to run simulation
    if st.sidebar.button("Run Simulation"):
        with st.spinner("Running simulation..."):
            try:
                st.session_state.results = run_simulation(st.session_state.params)
                st.session_state.animate = False
            except Exception as e:
                st.error(f"Error during simulation: {str(e)}")
                import traceback
                st.text(traceback.format_exc())
                # Initialize results with empty values to prevent further errors
                st.session_state.results = {
                    'events': [],
                    'queue_stats': [],
                    'zone_stats': {'A': [], 'B': [], 'C': []},
                    'total_time': 0
                }
    
    # Load/Save scenario
    st.sidebar.subheader("Save/Load Scenario")
    scenario_json = st.sidebar.text_area("Scenario JSON", value=str(st.session_state.params), height=150)
    
    if st.sidebar.button("Load Scenario"):
        try:
            # Parse the JSON string (using eval for simplicity in this demo)
            loaded_params = eval(scenario_json)
            st.session_state.params = loaded_params
            st.sidebar.success("Scenario loaded!")
        except Exception as e:
            st.sidebar.error(f"Error loading scenario: {e}")
    
    # Show results if available
    if st.session_state.results:
        # Summary statistics
        st.header("Simulation Results")
        
        # Two columns for summary and export
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Summary")
            st.write(f"Total Simulation Time: {st.session_state.results['total_time']:.2f} minutes")
            st.write(f"Number of EXP Riders: {st.session_state.params['nEXP']}")
            st.write(f"Number of FOC Riders: {st.session_state.params['nFOC']}")
            st.write(f"Riders per Zone: {st.session_state.params['capZone']}")
        
        with col2:
            st.subheader("Export Data")
            export_data = export_to_csv(st.session_state.results)
            
            # Export buttons
            st.download_button(
                label="Download Events CSV",
                data=export_data['events'],
                file_name=f"rider_events_{export_data['timestamp']}.csv",
                mime="text/csv",
            )
            
            st.download_button(
                label="Download Queue Stats CSV",
                data=export_data['queue_stats'],
                file_name=f"queue_stats_{export_data['timestamp']}.csv",
                mime="text/csv",
            )
            
            st.download_button(
                label="Download Zone Stats CSV",
                data=export_data['zone_stats'],
                file_name=f"zone_stats_{export_data['timestamp']}.csv",
                mime="text/csv",
            )
        
        # Create visualizations
        st.header("Visualizations")
        
        # Create tabs for different visualizations
        tab1, tab2, tab3, tab4 = st.tabs(["Gantt Chart", "Zone Utilization", "Queue Length", "Animation"])
        
        with tab1:
            gantt_fig = create_gantt_chart(st.session_state.results['events'])
            if gantt_fig:
                st.plotly_chart(gantt_fig, use_container_width=True)
            else:
                st.write("No data available for Gantt chart.")
        
        with tab2:
            util_fig = create_zone_utilization_chart(st.session_state.results['zone_stats'])
            if util_fig:
                st.plotly_chart(util_fig, use_container_width=True)
            else:
                st.write("No data available for zone utilization chart.")
        
        with tab3:
            queue_fig = create_queue_length_chart(st.session_state.results['queue_stats'])
            if queue_fig:
                st.plotly_chart(queue_fig, use_container_width=True)
            else:
                st.write("No data available for queue length chart.")
        
        with tab4:
            st.subheader("Track Animation")
            
            # Button to start/stop animation
            if st.button("Start Animation" if not st.session_state.animate else "Stop Animation"):
                st.session_state.animate = not st.session_state.animate
            
            # Animation speed
            animation_speed = st.slider("Animation Speed", 0.1, 5.0, 1.0, 0.1)
            
            # Progress bar for animation
            if st.session_state.animate:
                max_time = st.session_state.results['total_time']
                progress_bar = st.progress(0)
                
                # Animation container
                animation_container = st.empty()
                
                # Run animation
                time_step = 0.5 / animation_speed  # Time step in simulation minutes
                for t in np.arange(0, max_time + time_step, time_step):
                    if not st.session_state.animate:
                        break
                    
                    progress = min(t / max_time, 1.0)
                    progress_bar.progress(progress)
                    
                    with animation_container.container():
                        create_animation_frame(st.session_state.results['events'], t, st.session_state.params)
                    
                    # Actual sleep time (wall clock)
                    time.sleep(0.1)  # 100ms delay between frames
            else:
                # Show the first frame when not animating
                create_animation_frame(st.session_state.results['events'], 0, st.session_state.params)
    else:
        # Instructions
        st.header("Welcome to the Rider Training Track Simulation")
        st.write("""
        This simulator models a rider training track with three sequential practice zones.
        
        1. Configure the simulation parameters in the sidebar.
        2. Click "Run Simulation" to start.
        3. View results and visualizations.
        4. Export data for further analysis.
        
        **Rider Types:**
        - 🔴 INST: Instructor (always 1, demonstrates first)
        - 🟢 EXP: Experienced Riders
        - 🔵 FOC: Focus Riders (start after all EXP riders)
        
        **Track Layout:**
        Queue → Enter Gate → Zone A → Zone B → Zone C → Exit Gate
        """)
        
        # Text-based visualization instead of image
        st.markdown("""
        ```
        ┌──────────────────────── Track ────────────────────────┐
        │  ⏱ Enter time                                         │
        │  Zone A  (Slow Riding)   (dwell = tA)                 │
        │  Zone B  (Decision Making) (dwell = tB)               │
        │  Zone C  (Obstacle)        (dwell = tC)               │
        │  ⏱ Exit time (tExit)                                  │
        └───────────────────────────────────────────────────────┘
        
        Queue Line ▸ Entry Gate ▸ Zone A ▸ Zone B ▸ Zone C ▸ Exit Gate ▸ Queue Line
        ```
        """)

if __name__ == "__main__":
    main()
