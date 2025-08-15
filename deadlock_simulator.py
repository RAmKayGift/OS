import threading
import time
import random
import logging
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from tkinter import *
from tkinter import ttk, scrolledtext
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from queue import Queue
from collections import deque
import os
from datetime import datetime

# Configure logging
LOG_FILE = 'deadlock_simulation.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class Resource:
    def __init__(self, name):
        self.name = name
        self.lock = threading.Lock()
        self.owner = None
        self.waiting_threads = set()
        self.history = deque(maxlen=10)

    def acquire(self, thread, timeout=2):
        self.history.append(f"{thread.name} requesting {self.name}")
        if self.lock.acquire(timeout=timeout):
            self.owner = thread.name
            if thread.name in self.waiting_threads:
                self.waiting_threads.remove(thread.name)
            self.history.append(f"{thread.name} acquired {self.name}")
            return True
        else:
            if thread.name not in self.waiting_threads:
                self.waiting_threads.add(thread.name)
            self.history.append(f"{thread.name} waiting for {self.name}")
            return False

    def release(self, thread):
        if self.owner == thread.name:
            self.lock.release()
            self.history.append(f"{thread.name} released {self.name}")
            self.owner = None
            return True
        return False

class DeadlockDetector:
    def __init__(self, threads, resources):
        self.threads = threads
        self.resources = resources
        self.history = deque(maxlen=20)

    def build_allocation_graph(self):
        G = nx.DiGraph()
        for thread in self.threads:
            G.add_node(thread.name, type='thread', color='#4682B4', shape='s', size=2000)
        for resource in self.resources:
            G.add_node(resource.name, type='resource', color='#2E8B57', shape='d', size=2000)
        for resource in self.resources:
            if resource.owner:
                G.add_edge(resource.name, resource.owner, color='#006400', label='held', width=3)
            for thread_name in resource.waiting_threads:
                G.add_edge(thread_name, resource.name, color='#8B0000', label='waiting', width=3)
        return G

    def build_wait_for_graph(self):
        G = nx.DiGraph()
        for thread in self.threads:
            G.add_node(thread.name)
        for resource in self.resources:
            if resource.owner:
                for thread in self.threads:
                    if resource.name in thread.requested_resources and thread.name != resource.owner:
                        G.add_edge(thread.name, resource.owner)
        return G

    def detect_deadlock(self):
        G = self.build_wait_for_graph()
        try:
            cycle = nx.find_cycle(G)
            self.history.append(f"Deadlock detected: {cycle}")
            logging.warning(f"Deadlock detected: {cycle}")
            return cycle
        except nx.NetworkXNoCycle:
            return None

class SimulationThread(threading.Thread):
    def __init__(self, name, resources, status_queue, priority=1):
        super().__init__(name=name, daemon=True)
        self.priority = priority
        self.resources = {r.name: r for r in resources}
        self.status_queue = status_queue
        self.running = True
        self.paused = False
        self.requested_resources = set()
        self.held_resources = set()
        self.current_action = "Initializing"
        self.generate_new_actions()

    def generate_new_actions(self):
        self.actions = []
        available_resources = list(self.resources.keys())
        random.shuffle(available_resources)
        # create 2-4 action groups of acquire/release
        for i in range(random.randint(2, 4)):
            res = available_resources[i]
            self.actions.append((res, "acquire"))
            if random.random() > 0.5:
                another_res = random.choice([r for r in available_resources if r != res])
                self.actions.append((another_res, "acquire"))
                self.actions.append((res, "release"))
                self.actions.append((another_res, "release"))
            else:
                self.actions.append((res, "release"))

    def run(self):
        while self.running:
            if not self.paused and self.actions:
                resource_name, action_type = self.actions[0]
                self.current_action = f"{action_type} {resource_name}"
                if action_type == "acquire":
                    if self.acquire_resource(resource_name):
                        self.actions.pop(0)
                elif action_type == "release":
                    if self.release_resource(resource_name):
                        self.actions.pop(0)
                self.update_status()
                time.sleep(2.0)
            if not self.actions:
                self.generate_new_actions()
                time.sleep(1.0)

    def acquire_resource(self, resource_name):
        resource = self.resources[resource_name]
        if resource.acquire(self):
            self.held_resources.add(resource_name)
            self.requested_resources.discard(resource_name)
            return True
        else:
            self.requested_resources.add(resource_name)
            return False

    def release_resource(self, resource_name):
        resource = self.resources[resource_name]
        if resource.release(self):
            self.held_resources.discard(resource_name)
            return True
        return False

    def update_status(self):
        status = {
            'thread': self.name,
            'priority': self.priority,
            'held': list(self.held_resources),
            'waiting': list(self.requested_resources),
            'action': self.current_action
        }
        # Optionally log status updates (commented out to avoid overwhelming the log file)
        # logging.info(f"STATUS {status}")
        self.status_queue.put(('update', status))

class DeadlockSimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Deadlock Simulator")
        self.root.geometry("1400x900")
        self.simulation_running = False
        self.simulation_paused = False
        self.threads = []
        self.resources = []
        self.status_queue = Queue()
        self.detector = None
        self.auto_resolve = BooleanVar(value=True)
        self.deadlock_count = 0
        self.last_update = 0
        self.setup_ui()
        self.setup_animation()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side=LEFT, fill=Y)

        control_frame = ttk.LabelFrame(left_panel, text="Simulation Control", padding=10)
        control_frame.pack(fill=X, pady=(0, 10))
        ttk.Button(control_frame, text="▶ Start", command=self.start_simulation).pack(fill=X, pady=5)
        ttk.Button(control_frame, text="⏸ Pause", command=self.pause_simulation).pack(fill=X, pady=5)
        ttk.Button(control_frame, text="■ Stop", command=self.stop_simulation).pack(fill=X, pady=5)
        ttk.Button(control_frame, text="📜 View Logs", command=self.open_logs_window).pack(fill=X, pady=5)
        ttk.Checkbutton(control_frame, text="Auto-Resolve Deadlocks", variable=self.auto_resolve).pack(fill=X, pady=5)

        stats_frame = ttk.LabelFrame(left_panel, text="Statistics", padding=10)
        stats_frame.pack(fill=X, pady=(0, 10))
        self.stats_label = ttk.Label(stats_frame, text="Threads: 0\nResources: 0\nDeadlocks: 0\nStatus: Stopped")
        self.stats_label.pack()

        status_frame = ttk.LabelFrame(left_panel, text="Thread Status", padding=10)
        status_frame.pack(fill=BOTH, expand=True)
        columns = ('Thread', 'Priority', 'Held', 'Waiting', 'Action')
        self.status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.status_tree.heading(col, text=col)
            self.status_tree.column(col, width=90, anchor='center')
        scrollbar = ttk.Scrollbar(status_frame, orient=VERTICAL, command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.status_tree.pack(fill=BOTH, expand=True)

        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=RIGHT, fill=BOTH, expand=True)

        graph_frame = ttk.LabelFrame(right_panel, text="Live Resource Allocation Graph", padding=10)
        graph_frame.pack(fill=BOTH, expand=True)
        self.figure, self.ax = plt.subplots(figsize=(10, 6), tight_layout=True)
        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        log_frame = ttk.LabelFrame(right_panel, text="Event Log", padding=10)
        log_frame.pack(fill=BOTH, expand=False, pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=WORD, width=100, height=10, font=('Consolas', 9))
        self.log_text.pack(fill=BOTH, expand=True)

    # ----- Logs window and helpers -----
    def open_logs_window(self):
        """Open a Toplevel window that shows the contents of the log file and allows filtering."""
        win = Toplevel(self.root)
        win.title("Simulation Logs")
        win.geometry("1000x650")

        # Top frame for filters and controls
        top_frame = ttk.Frame(win)
        top_frame.pack(fill=X, padx=8, pady=8)

        ttk.Label(top_frame, text="Filter by Date:").pack(side=LEFT, padx=(0, 6))
        date_var = StringVar(value="All")
        dates = self.get_log_dates()
        date_combo = ttk.Combobox(top_frame, textvariable=date_var, values=["All"] + dates, state="readonly", width=16)
        date_combo.pack(side=LEFT, padx=(0, 10))

        ttk.Label(top_frame, text="Filter by Type:").pack(side=LEFT, padx=(0, 6))
        type_var = StringVar(value="All")
        type_combo = ttk.Combobox(top_frame, textvariable=type_var, values=["All", "Deadlock", "Resource Allocation"], state="readonly", width=18)
        type_combo.pack(side=LEFT, padx=(0, 10))

        refresh_btn = ttk.Button(top_frame, text="Refresh", command=lambda: self.load_logs(log_area, date_var.get(), type_var.get()))
        refresh_btn.pack(side=LEFT, padx=(0, 6))

        tail_btn = ttk.Button(top_frame, text="Tail (last 200 lines)", command=lambda: self.load_logs(log_area, date_var.get(), type_var.get(), tail_lines=200))
        tail_btn.pack(side=LEFT, padx=(0, 6))

        # Log display area
        log_area = scrolledtext.ScrolledText(win, wrap=WORD, font=('Consolas', 10))
        log_area.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))
        log_area.config(state=DISABLED)

        # Load initial logs
        self.load_logs(log_area, "All", "All")

    def get_log_dates(self):
        """Return sorted list of unique dates present in the log file (YYYY-MM-DD)."""
        if not os.path.exists(LOG_FILE):
            return []
        dates = set()
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split(" - ")
                    if not parts:
                        continue
                    dt_str = parts[0].strip()
                    try:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S,%f")
                        dates.add(dt.date().isoformat())
                    except Exception:
                        continue
        except Exception:
            return []
        return sorted(dates)

    def load_logs(self, log_area, date_filter="All", type_filter="All", tail_lines=None):
        """Load logs from the LOG_FILE into the provided text widget with optional filters."""
        log_area.config(state=NORMAL)
        log_area.delete(1.0, END)
        if not os.path.exists(LOG_FILE):
            log_area.insert(END, "No logs found.\n")
            log_area.config(state=DISABLED)
            return

        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                if tail_lines:
                    # Efficient tail: read from end in blocks
                    # Fallback to full read if any error
                    try:
                        f.seek(0, os.SEEK_END)
                        filesize = f.tell()
                        blocksize = 1024
                        data = b""
                        lines = []
                        with open(LOG_FILE, "rb") as fb:
                            fb.seek(0, os.SEEK_END)
                            pointer = fb.tell()
                            buffer = b""
                            while pointer > 0 and len(lines) <= tail_lines:
                                read_size = min(blocksize, pointer)
                                pointer -= read_size
                                fb.seek(pointer)
                                chunk = fb.read(read_size)
                                buffer = chunk + buffer
                                lines = buffer.splitlines()
                            lines = lines[-tail_lines:]
                            # decode and filter
                            for raw in lines:
                                try:
                                    line = raw.decode('utf-8', 'ignore')
                                except:
                                    line = raw.decode('latin-1', 'ignore')
                                if self._should_show_line(line, date_filter, type_filter):
                                    log_area.insert(END, line + "\n")
                    except Exception:
                        # fallback full read
                        f.seek(0)
                        for line in f:
                            if self._should_show_line(line, date_filter, type_filter):
                                log_area.insert(END, line)
                else:
                    for line in f:
                        if self._should_show_line(line, date_filter, type_filter):
                            log_area.insert(END, line)
        except Exception as e:
            log_area.insert(END, f"Error reading log file: {e}\n")
        log_area.config(state=DISABLED)
        # auto-scroll to end
        try:
            log_area.see(END)
        except:
            pass

    def _should_show_line(self, line, date_filter, type_filter):
        """Helper to decide whether to show a log line given filters."""
        show = True
        if date_filter and date_filter != "All":
            parts = line.split(" - ")
            if parts:
                dt_str = parts[0].strip()
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S,%f")
                    if dt.date().isoformat() != date_filter:
                        return False
                except Exception:
                    # if parse fails, fall back to showing the line
                    pass
        if type_filter == "Deadlock":
            if "DEADLOCK" not in line.upper() and "Deadlock" not in line:
                return False
        if type_filter == "Resource Allocation":
            if not any(x in line.lower() for x in ["acquired", "released", "requesting", "waiting"]):
                return False
        return show

    # ===== Existing unchanged methods (kept intact) =====
    def setup_animation(self):
        self.animation_running = True
        self.update_animation()

    def update_animation(self):
        if not self.simulation_running or self.simulation_paused:
            self.root.after(500, self.update_animation)
            return
        self.ax.clear()
        self.process_queue()
        if self.detector:
            G = self.detector.build_allocation_graph()
            if G.number_of_nodes() > 0:
                pos = nx.spring_layout(G, k=0.8, iterations=50)
                for node in G.nodes():
                    node_type = G.nodes[node]['type']
                    color = G.nodes[node]['color']
                    shape = G.nodes[node]['shape']
                    size = G.nodes[node]['size']
                    nx.draw_networkx_nodes(G, pos, nodelist=[node],
                                           node_shape=shape,
                                           node_size=size,
                                           node_color=color,
                                           edgecolors='black', linewidths=1)
                edge_colors = []
                edge_styles = []
                for u, v in G.edges():
                    edge_data = G.edges[u, v]
                    edge_colors.append(edge_data['color'])
                    if edge_data['label'] == 'waiting':
                        alpha = 0.3 + 0.7 * (0.5 + 0.5 * abs((time.time() % 2) - 1))
                        rgb = mcolors.to_rgb(edge_colors[-1])
                        edge_colors[-1] = (*rgb, alpha)
                        edge_styles.append((0, (5, 5)))
                    else:
                        edge_styles.append('solid')
                nx.draw_networkx_edges(G, pos, edge_color=edge_colors,
                                       width=3, style=edge_styles,
                                       arrows=True, arrowstyle='-|>',
                                       arrowsize=15)
                nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
                edge_labels = {(u, v): G.edges[u, v]['label'] for (u, v) in G.edges()}
                nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                             font_size=9, font_weight='bold',
                                             bbox=dict(alpha=0.7))
                try:
                    cycle = nx.find_cycle(self.detector.build_wait_for_graph())
                    self.ax.set_title("⚡ DEADLOCK DETECTED! ⚡", color='red', fontweight='bold', fontsize=14,
                                      bbox=dict(facecolor='yellow', alpha=0.5))
                    if int(time.time()) % 2 == 0:
                        nx.draw_networkx_edges(G, pos, edgelist=cycle,
                                               edge_color='red', width=5,
                                               alpha=0.7, arrows=True)
                    if self.auto_resolve.get():
                        self.resolve_deadlock()
                except nx.NetworkXNoCycle:
                    self.ax.set_title("✓ System Running Normally", color='green', fontweight='bold', fontsize=14)
            self.canvas.draw()
        self.root.after(500, self.update_animation)

    def process_queue(self):
        while not self.status_queue.empty():
            action, data = self.status_queue.get()
            if action == 'update':
                thread_items = {self.status_tree.item(item)['values'][0]: item
                                for item in self.status_tree.get_children()}
                values = (
                    data['thread'],
                    data['priority'],
                    ', '.join(data['held']) if data['held'] else 'None',
                    ', '.join(data['waiting']) if data['waiting'] else 'None',
                    data['action']
                )
                if data['thread'] in thread_items:
                    self.status_tree.item(thread_items[data['thread']], values=values)
                else:
                    self.status_tree.insert('', 'end', values=values)

    def start_simulation(self):
        if self.simulation_running:
            return
        self.log("===== Starting simulation =====")
        self.resources = [Resource(f"R{i}") for i in range(1, 6)]
        self.threads = [
            SimulationThread(f"T-{i}", self.resources, self.status_queue, priority=random.randint(1, 10))
            for i in range(1, 6)
        ]
        self.detector = DeadlockDetector(self.threads, self.resources)
        for thread in self.threads:
            thread.start()
        self.simulation_running = True
        self.simulation_paused = False
        self.deadlock_count = 0
        self.update_stats()

    def pause_simulation(self):
        if not self.simulation_running:
            return
        self.simulation_paused = not self.simulation_paused
        for thread in self.threads:
            thread.paused = self.simulation_paused
        self.log("Simulation paused" if self.simulation_paused else "Simulation resumed")
        self.update_stats()

    def stop_simulation(self):
        if not self.simulation_running:
            return
        self.log("===== Stopping simulation =====")
        self.simulation_running = False
        for thread in self.threads:
            thread.running = False
        self.status_tree.delete(*self.status_tree.get_children())
        self.ax.clear()
        self.canvas.draw()
        self.threads = []
        self.resources = []
        self.detector = None
        self.update_stats()

    def resolve_deadlock(self):
        if not self.simulation_running or self.simulation_paused:
            return
        if time.time() - self.last_update < 3:
            return
        cycle = self.detector.detect_deadlock()
        if cycle:
            self.deadlock_count += 1
            self.last_update = time.time()
            self.log(f"⚡ DEADLOCK DETECTED! Cycle: {cycle}")
            self.log("Resolving deadlock based on priorities...")
            threads_in_cycle = list({node for edge in cycle for node in edge if node.startswith("T-")})
            if not threads_in_cycle:
                return
            thread_to_keep = max(
                (t for t in self.threads if t.name in threads_in_cycle),
                key=lambda t: t.priority
            )
            self.log(f"Highest priority thread: {thread_to_keep.name} (Priority {thread_to_keep.priority})")
            # Terminate lower priority threads in cycle and restart them
            for thread in list(self.threads):
                if thread.name in threads_in_cycle and thread is not thread_to_keep:
                    thread.running = False
                    for resource_name in list(thread.held_resources):
                        thread.release_resource(resource_name)
                    self.log(f"Terminated {thread.name} to free resources")
                    try:
                        self.threads.remove(thread)
                    except ValueError:
                        pass
                    # restart same-named thread
                    new_thread = SimulationThread(thread.name, self.resources, self.status_queue, priority=thread.priority)
                    new_thread.start()
                    self.threads.append(new_thread)
            self.detector.threads = self.threads
            self.update_stats()

    def update_stats(self):
        status = "Running" if not self.simulation_paused else "Paused"
        stats_text = (f"Threads: {len(self.threads)}\n"
                      f"Resources: {len(self.resources)}\n"
                      f"Deadlocks: {self.deadlock_count}\n"
                      f"Status: {status}")
        self.stats_label.config(text=stats_text)

    def log(self, message):
        """Write to the GUI event log and also append to the log file via logging.info."""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.config(state=DISABLED)
        self.log_text.see(END)
        # Also write to the file logger (so the View Logs window can read it)
        try:
            logging.info(message)
        except Exception:
            pass

if __name__ == "__main__":
    root = Tk()
    app = DeadlockSimulatorGUI(root)
    root.mainloop()
