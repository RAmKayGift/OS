import threading
import time
import random
import logging
import json
import os
from datetime import datetime, timedelta
from collections import deque, defaultdict
from queue import Queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import math

# Configure enhanced logging
LOG_FILE = 'enhanced_deadlock_simulation.log'
METRICS_FILE = 'deadlock_metrics.json'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class PerformanceMetrics:
    """Advanced performance tracking and analytics"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.deadlock_count = 0
        self.total_requests = 0
        self.successful_acquisitions = 0
        self.failed_acquisitions = 0
        self.total_wait_time = 0
        self.resolution_times = []
        self.detection_times = []
        self.throughput_samples = deque(maxlen=100)
        self.resource_utilization = defaultdict(float)
        self.thread_performance = defaultdict(lambda: {'requests': 0, 'success': 0, 'wait_time': 0})
        self.start_time = time.time()
        self.deadlock_intervals = []
        self.last_deadlock_time = 0
        
    def record_request(self, thread_name, resource_name):
        self.total_requests += 1
        self.thread_performance[thread_name]['requests'] += 1
        
    def record_acquisition(self, thread_name, resource_name, wait_time=0):
        self.successful_acquisitions += 1
        self.thread_performance[thread_name]['success'] += 1
        self.thread_performance[thread_name]['wait_time'] += wait_time
        self.total_wait_time += wait_time
        
    def record_failed_acquisition(self, thread_name, resource_name):
        self.failed_acquisitions += 1
        
    def record_deadlock_detection(self, detection_time):
        self.deadlock_count += 1
        self.detection_times.append(detection_time)
        current_time = time.time()
        if self.last_deadlock_time > 0:
            self.deadlock_intervals.append(current_time - self.last_deadlock_time)
        self.last_deadlock_time = current_time
        
    def record_deadlock_resolution(self, resolution_time):
        self.resolution_times.append(resolution_time)
        
    def update_throughput(self):
        current_time = time.time()
        self.throughput_samples.append((current_time, self.successful_acquisitions))
        
    def get_current_metrics(self):
        runtime = time.time() - self.start_time
        avg_wait_time = self.total_wait_time / max(1, self.successful_acquisitions)
        success_rate = (self.successful_acquisitions / max(1, self.total_requests)) * 100
        throughput = self.successful_acquisitions / max(1, runtime) * 60  # per minute
        
        avg_detection_time = sum(self.detection_times) / max(1, len(self.detection_times))
        avg_resolution_time = sum(self.resolution_times) / max(1, len(self.resolution_times))
        
        deadlock_frequency = self.deadlock_count / max(1, runtime) * 3600  # per hour
        avg_deadlock_interval = sum(self.deadlock_intervals) / max(1, len(self.deadlock_intervals))
        
        return {
            'runtime': runtime,
            'deadlocks': self.deadlock_count,
            'total_requests': self.total_requests,
            'success_rate': success_rate,
            'avg_wait_time': avg_wait_time,
            'throughput': throughput,
            'avg_detection_time': avg_detection_time,
            'avg_resolution_time': avg_resolution_time,
            'deadlock_frequency': deadlock_frequency,
            'avg_deadlock_interval': avg_deadlock_interval
        }
    
    def save_to_file(self):
        """Save metrics to JSON file for analysis"""
        metrics_data = {
            'timestamp': datetime.now().isoformat(),
            'metrics': self.get_current_metrics(),
            'thread_performance': dict(self.thread_performance),
            'detection_times': self.detection_times,
            'resolution_times': self.resolution_times,
            'deadlock_intervals': self.deadlock_intervals
        }
        
        try:
            with open(METRICS_FILE, 'w') as f:
                json.dump(metrics_data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save metrics: {e}")

class AdvancedResource:
    """Enhanced resource with priority queues and smart allocation"""
    def __init__(self, name, max_instances=1):
        self.name = name
        self.max_instances = max_instances
        self.current_instances = max_instances
        self.lock = threading.Lock()
        self.owners = set()
        self.waiting_queue = []  # Priority queue: (priority, timestamp, thread_name)
        self.history = deque(maxlen=20)
        self.allocation_count = 0
        self.total_hold_time = 0
        self.last_allocation_time = {}
        
    def request_resource(self, thread, priority=1, timeout=3):
        """Smart resource request with priority and timeout"""
        request_time = time.time()
        self.history.append(f"{thread.name} requesting {self.name} (priority: {priority})")
        
        with self.lock:
            if self.current_instances > 0:
                # Resource available immediately
                self.current_instances -= 1
                self.owners.add(thread.name)
                self.allocation_count += 1
                self.last_allocation_time[thread.name] = request_time
                self.history.append(f"{thread.name} acquired {self.name} immediately")
                return True
            else:
                # Add to priority queue
                self.waiting_queue.append((priority, request_time, thread.name))
                self.waiting_queue.sort(key=lambda x: (-x[0], x[1]))  # Higher priority first, then FIFO
                self.history.append(f"{thread.name} added to waiting queue (priority: {priority})")
                return False
    
    def release_resource(self, thread):
        """Release resource and allocate to next waiting thread"""
        with self.lock:
            if thread.name in self.owners:
                self.owners.remove(thread.name)
                self.current_instances += 1
                
                # Track hold time
                if thread.name in self.last_allocation_time:
                    hold_time = time.time() - self.last_allocation_time[thread.name]
                    self.total_hold_time += hold_time
                    del self.last_allocation_time[thread.name]
                
                self.history.append(f"{thread.name} released {self.name}")
                
                # Allocate to next waiting thread if any
                if self.waiting_queue and self.current_instances > 0:
                    _, _, next_thread = self.waiting_queue.pop(0)
                    self.current_instances -= 1
                    self.owners.add(next_thread)
                    self.allocation_count += 1
                    self.last_allocation_time[next_thread] = time.time()
                    self.history.append(f"{next_thread} acquired {self.name} from queue")
                
                return True
        return False
    
    def get_waiting_threads(self):
        """Get list of threads waiting for this resource"""
        with self.lock:
            return [thread_name for _, _, thread_name in self.waiting_queue]
    
    def get_utilization_stats(self):
        """Get resource utilization statistics"""
        total_capacity = self.max_instances
        current_usage = self.max_instances - self.current_instances
        utilization = (current_usage / total_capacity) * 100 if total_capacity > 0 else 0
        
        avg_hold_time = self.total_hold_time / max(1, self.allocation_count)
        
        return {
            'utilization': utilization,
            'current_usage': current_usage,
            'total_capacity': total_capacity,
            'allocations': self.allocation_count,
            'avg_hold_time': avg_hold_time,
            'waiting_count': len(self.waiting_queue)
        }

class SmartDeadlockDetector:
    """Advanced deadlock detection with multiple algorithms"""
    def __init__(self, threads, resources, metrics):
        self.threads = threads
        self.resources = resources
        self.metrics = metrics
        self.detection_history = deque(maxlen=50)
        self.false_positives = 0
        self.detection_cache = {}
        self.cache_timeout = 1.0  # Cache results for 1 second
        
    def build_resource_allocation_matrix(self):
        """Build classical RAG matrix representation"""
        n_threads = len(self.threads)
        n_resources = len(self.resources)
        
        # Allocation Matrix: allocation[i][j] = resources of type j allocated to thread i
        allocation = [[0 for _ in range(n_resources)] for _ in range(n_threads)]
        
        # Request Matrix: request[i][j] = resources of type j requested by thread i
        request = [[0 for _ in range(n_resources)] for _ in range(n_threads)]
        
        # Available Vector: available[j] = available instances of resource j
        available = [0 for _ in range(n_resources)]
        
        thread_index = {thread.name: i for i, thread in enumerate(self.threads)}
        resource_index = {resource.name: j for j, resource in enumerate(self.resources)}
        
        # Fill matrices
        for j, resource in enumerate(self.resources):
            available[j] = resource.current_instances
            
            # Allocation matrix
            for owner in resource.owners:
                if owner in thread_index:
                    allocation[thread_index[owner]][j] += 1
            
            # Request matrix
            for waiting_thread in resource.get_waiting_threads():
                if waiting_thread in thread_index:
                    request[thread_index[waiting_thread]][j] += 1
        
        return allocation, request, available, thread_index, resource_index
    
    def banker_algorithm_check(self):
        """Use Banker's algorithm for deadlock prevention check"""
        allocation, request, available, thread_index, _ = self.build_resource_allocation_matrix()
        n_threads = len(self.threads)
        n_resources = len(self.resources)
        
        # Calculate Need matrix: need[i][j] = max_need[i][j] - allocation[i][j]
        # For simplicity, assume each thread needs at most 2 of each resource
        max_need = [[2 for _ in range(n_resources)] for _ in range(n_threads)]
        need = [[max_need[i][j] - allocation[i][j] for j in range(n_resources)] for i in range(n_threads)]
        
        # Safety algorithm
        work = available[:]
        finish = [False] * n_threads
        safe_sequence = []
        
        while len(safe_sequence) < n_threads:
            found = False
            for i in range(n_threads):
                if not finish[i] and all(need[i][j] <= work[j] for j in range(n_resources)):
                    # Thread i can complete
                    for j in range(n_resources):
                        work[j] += allocation[i][j]
                    finish[i] = True
                    safe_sequence.append(self.threads[i].name)
                    found = True
                    break
            
            if not found:
                # System is in unsafe state (potential deadlock)
                return False, []
        
        return True, safe_sequence
    
    def build_wait_for_graph(self):
        """Build enhanced wait-for graph with edge weights"""
        graph = defaultdict(list)
        edge_weights = {}
        
        for resource in self.resources:
            owners = list(resource.owners)
            waiting = resource.get_waiting_threads()
            
            for waiter in waiting:
                for owner in owners:
                    if waiter != owner:
                        graph[waiter].append(owner)
                        # Weight based on priority and wait time
                        wait_time = 1.0  # Simplified
                        edge_weights[(waiter, owner)] = wait_time
        
        return graph, edge_weights
    
    def detect_deadlock_dfs(self):
        """Enhanced cycle detection using DFS with path tracking"""
        current_time = time.time()
        
        # Check cache first
        if current_time - self.detection_cache.get('timestamp', 0) < self.cache_timeout:
            return self.detection_cache.get('result')
        
        start_time = time.time()
        graph, edge_weights = self.build_wait_for_graph()
        
        if not graph:
            result = None
        else:
            visited = set()
            rec_stack = set()
            path = []
            result = None
            
            def dfs(node, current_path):
                nonlocal result
                if result:
                    return
                
                visited.add(node)
                rec_stack.add(node)
                current_path.append(node)
                
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        dfs(neighbor, current_path[:])
                    elif neighbor in rec_stack:
                        # Found cycle
                        cycle_start = current_path.index(neighbor)
                        cycle = current_path[cycle_start:] + [neighbor]
                        result = cycle
                        return
                
                rec_stack.remove(node)
            
            for node in graph:
                if node not in visited:
                    dfs(node, [])
                    if result:
                        break
        
        detection_time = time.time() - start_time
        self.metrics.record_deadlock_detection(detection_time)
        
        # Cache result
        self.detection_cache = {
            'result': result,
            'timestamp': current_time
        }
        
        if result:
            self.detection_history.append({
                'timestamp': datetime.now().isoformat(),
                'cycle': result,
                'detection_time': detection_time
            })
            logging.warning(f"DEADLOCK DETECTED: Cycle {result} (detection time: {detection_time:.3f}s)")
        
        return result
    
    def get_detection_efficiency(self):
        """Calculate detection algorithm efficiency metrics"""
        if not self.detection_history:
            return {}
        
        recent_detections = list(self.detection_history)[-10:]  # Last 10 detections
        detection_times = [d['detection_time'] for d in recent_detections]
        
        return {
            'avg_detection_time': sum(detection_times) / len(detection_times),
            'min_detection_time': min(detection_times),
            'max_detection_time': max(detection_times),
            'total_detections': len(self.detection_history),
            'false_positives': self.false_positives
        }

class DeadlockResolver:
    """Advanced deadlock resolution strategies"""
    def __init__(self, metrics):
        self.metrics = metrics
        self.resolution_strategies = ['priority_based', 'minimal_cost', 'youngest_first']
        self.current_strategy = 'priority_based'
        self.resolution_history = deque(maxlen=30)
        
    def resolve_deadlock(self, cycle, threads, resources):
        """Resolve deadlock using selected strategy"""
        start_time = time.time()
        
        if self.current_strategy == 'priority_based':
            result = self._priority_based_resolution(cycle, threads, resources)
        elif self.current_strategy == 'minimal_cost':
            result = self._minimal_cost_resolution(cycle, threads, resources)
        else:  # youngest_first
            result = self._youngest_first_resolution(cycle, threads, resources)
        
        resolution_time = time.time() - start_time
        self.metrics.record_deadlock_resolution(resolution_time)
        
        self.resolution_history.append({
            'timestamp': datetime.now().isoformat(),
            'strategy': self.current_strategy,
            'cycle': cycle,
            'victim': result.get('victim') if result else None,
            'resolution_time': resolution_time
        })
        
        return result
    
    def _priority_based_resolution(self, cycle, threads, resources):
        """Terminate lowest priority thread in cycle"""
        threads_in_cycle = [t for t in threads if t.name in cycle]
        if not threads_in_cycle:
            return None
        
        # Find thread with lowest priority
        victim = min(threads_in_cycle, key=lambda t: t.priority)
        
        logging.info(f"PRIORITY-BASED RESOLUTION: Terminating {victim.name} (priority: {victim.priority})")
        
        # Release all resources held by victim
        released_resources = []
        for resource in resources:
            if victim.name in resource.owners:
                resource.release_resource(victim)
                released_resources.append(resource.name)
        
        # Restart the thread
        victim.restart()
        
        return {
            'strategy': 'priority_based',
            'victim': victim.name,
            'released_resources': released_resources
        }
    
    def _minimal_cost_resolution(self, cycle, threads, resources):
        """Select victim based on minimal resource cost"""
        threads_in_cycle = [t for t in threads if t.name in cycle]
        if not threads_in_cycle:
            return None
        
        # Calculate cost for each thread (number of resources held)
        thread_costs = {}
        for thread in threads_in_cycle:
            cost = len(thread.held_resources)
            thread_costs[thread.name] = cost
        
        # Select thread with minimal cost
        victim_name = min(thread_costs, key=thread_costs.get)
        victim = next(t for t in threads_in_cycle if t.name == victim_name)
        
        logging.info(f"MINIMAL-COST RESOLUTION: Terminating {victim.name} (cost: {thread_costs[victim_name]})")
        
        # Release resources and restart
        released_resources = []
        for resource in resources:
            if victim.name in resource.owners:
                resource.release_resource(victim)
                released_resources.append(resource.name)
        
        victim.restart()
        
        return {
            'strategy': 'minimal_cost',
            'victim': victim.name,
            'cost': thread_costs[victim_name],
            'released_resources': released_resources
        }
    
    def _youngest_first_resolution(self, cycle, threads, resources):
        """Terminate the youngest (most recently started) thread"""
        threads_in_cycle = [t for t in threads if t.name in cycle]
        if not threads_in_cycle:
            return None
        
        # Find most recently started thread
        victim = max(threads_in_cycle, key=lambda t: t.start_time)
        
        logging.info(f"YOUNGEST-FIRST RESOLUTION: Terminating {victim.name}")
        
        # Release resources and restart
        released_resources = []
        for resource in resources:
            if victim.name in resource.owners:
                resource.release_resource(victim)
                released_resources.append(resource.name)
        
        victim.restart()
        
        return {
            'strategy': 'youngest_first',
            'victim': victim.name,
            'released_resources': released_resources
        }

class EnhancedSimulationThread(threading.Thread):
    """Smart thread with adaptive behavior and learning"""
    def __init__(self, name, resources, status_queue, metrics, priority=1):
        super().__init__(name=name, daemon=True)
        self.priority = priority
        self.resources = {r.name: r for r in resources}
        self.status_queue = status_queue
        self.metrics = metrics
        self.running = True
        self.paused = False
        self.requested_resources = set()
        self.held_resources = set()
        self.current_action = "Initializing"
        self.start_time = time.time()
        self.action_history = deque(maxlen=20)
        self.success_rates = defaultdict(float)
        self.adaptive_delay = 1.0
        self.backoff_multiplier = 1.5
        self.max_backoff = 10.0
        self.consecutive_failures = 0
        self.generate_smart_actions()

    def generate_smart_actions(self):
        """Generate intelligent action sequences based on learning"""
        self.actions = []
        available_resources = list(self.resources.keys())
        
        # Adaptive resource selection based on success history
        sorted_resources = sorted(available_resources, 
                                key=lambda r: self.success_rates.get(r, 0.5), 
                                reverse=True)
        
        # Create 2-5 action groups with smart ordering
        num_groups = random.randint(2, 5)
        for i in range(num_groups):
            if i < len(sorted_resources):
                primary_resource = sorted_resources[i]
                self.actions.append((primary_resource, "acquire", self.priority))
                
                # Sometimes acquire a second resource
                if random.random() > 0.6 and len(sorted_resources) > i + 1:
                    secondary_resource = sorted_resources[i + 1]
                    self.actions.append((secondary_resource, "acquire", self.priority - 1))
                    
                    # Hold for random time then release in reverse order
                    self.actions.append((secondary_resource, "release", 0))
                    self.actions.append((primary_resource, "release", 0))
                else:
                    self.actions.append((primary_resource, "release", 0))
    
    def run(self):
        while self.running:
            try:
                if not self.paused and self.actions:
                    resource_name, action_type, action_priority = self.actions[0]
                    self.current_action = f"{action_type} {resource_name}"
                    
                    success = False
                    if action_type == "acquire":
                        success = self.smart_acquire_resource(resource_name, action_priority)
                    elif action_type == "release":
                        success = self.release_resource(resource_name)
                    
                    if success:
                        self.actions.pop(0)
                        self.consecutive_failures = 0
                        self.adaptive_delay = max(0.5, self.adaptive_delay * 0.9)  # Reduce delay on success
                    else:
                        self.consecutive_failures += 1
                        self.adaptive_delay = min(self.max_backoff, self.adaptive_delay * self.backoff_multiplier)
                    
                    self.action_history.append((resource_name, action_type, success, time.time()))
                    self.update_success_rates(resource_name, success)
                    self.update_status()
                    
                    # Adaptive sleep based on performance
                    time.sleep(self.adaptive_delay)
                
                if not self.actions:
                    self.generate_smart_actions()
                    time.sleep(1.0)
                    
            except Exception as e:
                logging.error(f"Thread {self.name} encountered error: {e}")
                time.sleep(2.0)
    
    def smart_acquire_resource(self, resource_name, priority):
        """Smart resource acquisition with metrics and timeout"""
        request_start = time.time()
        resource = self.resources[resource_name]
        
        self.metrics.record_request(self.name, resource_name)
        
        # Dynamic timeout based on system load
        base_timeout = 3.0
        load_factor = min(2.0, len(self.requested_resources) * 0.5 + 1.0)
        timeout = base_timeout * load_factor
        
        success = resource.request_resource(self, priority, timeout)
        
        wait_time = time.time() - request_start
        
        if success:
            self.held_resources.add(resource_name)
            self.requested_resources.discard(resource_name)
            self.metrics.record_acquisition(self.name, resource_name, wait_time)
            logging.info(f"{self.name} acquired {resource_name} (wait: {wait_time:.2f}s)")
        else:
            self.requested_resources.add(resource_name)
            self.metrics.record_failed_acquisition(self.name, resource_name)
            logging.debug(f"{self.name} failed to acquire {resource_name} (timeout: {timeout:.2f}s)")
        
        return success
    
    def release_resource(self, resource_name):
        """Release resource with logging"""
        resource = self.resources[resource_name]
        if resource.release_resource(self):
            self.held_resources.discard(resource_name)
            logging.info(f"{self.name} released {resource_name}")
            return True
        return False
    
    def update_success_rates(self, resource_name, success):
        """Update resource success rates for learning"""
        current_rate = self.success_rates[resource_name]
        # Exponential moving average
        self.success_rates[resource_name] = current_rate * 0.8 + (1.0 if success else 0.0) * 0.2
    
    def restart(self):
        """Restart thread after deadlock resolution"""
        self.requested_resources.clear()
        self.held_resources.clear()
        self.consecutive_failures = 0
        self.adaptive_delay = 1.0
        self.start_time = time.time()
        self.generate_smart_actions()
        logging.info(f"Thread {self.name} restarted")
    
    def update_status(self):
        """Update thread status for monitoring"""
        efficiency = len([h for h in self.action_history if h[2]]) / max(1, len(self.action_history)) * 100
        
        status = {
            'thread': self.name,
            'priority': self.priority,
            'held': list(self.held_resources),
            'waiting': list(self.requested_resources),
            'action': self.current_action,
            'efficiency': f"{efficiency:.1f}%",
            'delay': f"{self.adaptive_delay:.1f}s"
        }
        
        self.status_queue.put(('update', status))

class BeautifulDeadlockGUI:
    """Modern, beautiful GUI for the Enhanced Deadlock Simulator"""
    
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_styles()
        
        # Core components
        self.simulation_running = False
        self.simulation_paused = False
        self.threads = []
        self.resources = []
        self.metrics = PerformanceMetrics()
        self.detector = None
        self.resolver = None
        self.status_queue = Queue()
        self.auto_resolve = tk.BooleanVar(value=True)
        
        # Animation variables
        self.animation_running = True
        self.deadlock_flash = False
        self.update_counter = 0
        
        self.create_widgets()
        self.start_animation_loop()
        
    def setup_window(self):
        """Setup main window with modern styling"""
        self.root.title("🔄 Enhanced Deadlock Detection & Resolution Simulator")
        self.root.geometry("1600x1000")
        self.root.minsize(1200, 800)
        
        # Modern color scheme
        self.colors = {
            'bg_primary': '#1e1e2e',
            'bg_secondary': '#313244', 
            'bg_tertiary': '#45475a',
            'accent': '#89b4fa',
            'success': '#a6e3a1',
            'warning': '#f9e2af',
            'danger': '#f38ba8',
            'text_primary': '#cdd6f4',
            'text_secondary': '#a6adc8'
        }
        
        self.root.configure(bg=self.colors['bg_primary'])
        
    def setup_styles(self):
        """Setup modern ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles with modern colors
        style.configure('Title.TLabel', 
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 16, 'bold'))
        
        style.configure('Header.TLabel',
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['accent'],
                       font=('Segoe UI', 12, 'bold'))
        
        style.configure('Modern.TFrame',
                       background=self.colors['bg_secondary'],
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Card.TFrame',
                       background=self.colors['bg_tertiary'],
                       relief='flat',
                       borderwidth=2)
        
        style.map('Modern.TButton',
                 background=[('active', self.colors['accent']),
                           ('pressed', self.colors['accent'])],
                 foreground=[('active', self.colors['bg_primary'])])
    
    def create_widgets(self):
        """Create all GUI widgets with modern design"""
        
        # Main container
        main_container = ttk.Frame(self.root, style='Modern.TFrame')
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(main_container, 
                               text="🔄 Enhanced Deadlock Detection & Resolution Simulator",
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create paned window for resizable layout
        paned_window = ttk.PanedWindow(main_container, orient='horizontal')
        paned_window.pack(fill='both', expand=True)
        
        # Left panel
        self.create_left_panel(paned_window)
        
        # Right panel  
        self.create_right_panel(paned_window)
        
    def create_left_panel(self, parent):
        """Create left control panel"""
        left_frame = ttk.Frame(parent, style='Modern.TFrame', width=400)
        parent.add(left_frame, weight=1)
        
        # Control Section
        control_frame = ttk.LabelFrame(left_frame, text="🎮 Simulation Controls", 
                                      style='Card.TFrame', padding=15)
        control_frame.pack(fill='x', pady=(0, 15))
        
        # Control buttons with emojis and modern styling
        btn_style = {'width': 25, 'padding': (10, 5)}
        
        self.start_btn = ttk.Button(control_frame, text="▶️ Start Simulation", 
                                           command=self.start_simulation, **btn_style)
        self.start_btn.pack(fill='x', pady=5)
        
        self.pause_btn = ttk.Button(control_frame, text="⏸️ Pause", 
                                   command=self.pause_simulation, **btn_style)
        self.pause_btn.pack(fill='x', pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", 
                                  command=self.stop_simulation, **btn_style)
        self.stop_btn.pack(fill='x', pady=5)
        
        # Settings
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill='x', pady=10)
        
        auto_resolve_cb = ttk.Checkbutton(settings_frame, text="🔧 Auto-Resolve Deadlocks", 
                                         variable=self.auto_resolve)
        auto_resolve_cb.pack(anchor='w')
        
        # Statistics Section
        stats_frame = ttk.LabelFrame(left_frame, text="📊 Live Statistics", 
                                    style='Card.TFrame', padding=15)
        stats_frame.pack(fill='x', pady=(0, 15))
        
        self.stats_text = tk.Text(stats_frame, height=8, width=35,
                                 bg=self.colors['bg_primary'],
                                 fg=self.colors['text_primary'],
                                 font=('Consolas', 10),
                                 relief='flat', borderwidth=0)
        self.stats_text.pack(fill='both', expand=True)
        
        # Thread Status Section
        thread_frame = ttk.LabelFrame(left_frame, text="🧵 Thread Status", 
                                     style='Card.TFrame', padding=15)
        thread_frame.pack(fill='both', expand=True)
        
        # Create treeview with modern styling
        columns = ('Thread', 'Priority', 'Held', 'Waiting', 'Action', 'Efficiency')
        self.thread_tree = ttk.Treeview(thread_frame, columns=columns, show='headings',
                                       height=12, style='Modern.Treeview')
        
        # Configure columns
        for col in columns:
            self.thread_tree.heading(col, text=col)
            if col == 'Thread':
                self.thread_tree.column(col, width=120, anchor='w')
            elif col in ['Priority', 'Efficiency']:
                self.thread_tree.column(col, width=80, anchor='center')
            else:
                self.thread_tree.column(col, width=100, anchor='center')
        
        # Scrollbar for treeview
        tree_scroll = ttk.Scrollbar(thread_frame, orient='vertical', 
                                   command=self.thread_tree.yview)
        self.thread_tree.configure(yscrollcommand=tree_scroll.set)
        
        tree_scroll.pack(side='right', fill='y')
        self.thread_tree.pack(fill='both', expand=True)
    
    def create_right_panel(self, parent):
        """Create right panel with visualizations"""
        right_frame = ttk.Frame(parent, style='Modern.TFrame')
        parent.add(right_frame, weight=2)
        
        # Resource Allocation Visualization
        viz_frame = ttk.LabelFrame(right_frame, text="🎯 Live Resource Allocation Graph", 
                                  style='Card.TFrame', padding=15)
        viz_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Custom canvas for resource visualization
        self.viz_canvas = tk.Canvas(viz_frame, 
                                   bg=self.colors['bg_primary'],
                                   highlightthickness=0,
                                   relief='flat')
        self.viz_canvas.pack(fill='both', expand=True)
        
        # Event Log Section
        log_frame = ttk.LabelFrame(right_frame, text="📝 Event Log", 
                                  style='Card.TFrame', padding=15)
        log_frame.pack(fill='x', pady=(0, 10))
        
        # Create scrolled text for logs with modern styling
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12,
                                                 bg=self.colors['bg_primary'],
                                                 fg=self.colors['text_primary'],
                                                 font=('Consolas', 9),
                                                 relief='flat', borderwidth=0,
                                                 wrap='word')
        self.log_text.pack(fill='both', expand=True)
        
        # Configure text tags for colored logging
        self.log_text.tag_configure('deadlock', foreground=self.colors['danger'], font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure('success', foreground=self.colors['success'])
        self.log_text.tag_configure('warning', foreground=self.colors['warning'])
        self.log_text.tag_configure('info', foreground=self.colors['text_secondary'])
        
        # Performance Metrics Section
        perf_frame = ttk.LabelFrame(right_frame, text="⚡ Performance Metrics", 
                                   style='Card.TFrame', padding=15)
        perf_frame.pack(fill='x')
        
        self.metrics_text = tk.Text(perf_frame, height=6,
                                   bg=self.colors['bg_primary'],
                                   fg=self.colors['text_primary'],
                                   font=('Consolas', 10),
                                   relief='flat', borderwidth=0)
        self.metrics_text.pack(fill='both', expand=True)
    
    def start_simulation(self):
        """Start the enhanced simulation"""
        if self.simulation_running:
            self.log_message("⚠️ Simulation already running!", 'warning')
            return
        
        self.log_message("🚀 Starting Enhanced Deadlock Simulation...", 'success')
        
        # Create advanced resources
        resource_configs = [
            ("Database", 2, self.colors['danger']), 
            ("FileSystem", 1, self.colors['warning']), 
            ("NetworkPort", 3, self.colors['accent']), 
            ("Memory", 4, self.colors['success']), 
            ("Cache", 2, self.colors['text_primary']), 
            ("Logger", 1, self.colors['text_secondary'])
        ]
        
        self.resources = []
        for name, capacity, color in resource_configs:
            resource = AdvancedResource(name, capacity)
            resource.color = color  # Add color for visualization
            self.resources.append(resource)
        
        # Create smart threads
        thread_configs = [
            ("HighPri-1", 10), ("HighPri-2", 9),
            ("MedPri-1", 5), ("MedPri-2", 5), ("MedPri-3", 4),
            ("LowPri-1", 1), ("LowPri-2", 2)
        ]
        
        self.threads = []
        for name, priority in thread_configs:
            thread = EnhancedSimulationThread(name, self.resources, self.status_queue, 
                                            self.metrics, priority)
            self.threads.append(thread)
        
        # Initialize detector and resolver
        self.detector = SmartDeadlockDetector(self.threads, self.resources, self.metrics)
        self.resolver = DeadlockResolver(self.metrics)
        
        # Reset metrics and start threads
        self.metrics.reset()
        for thread in self.threads:
            thread.start()
        
        self.simulation_running = True
        self.simulation_paused = False
        
        # Update UI
        self.start_btn.configure(state='disabled')
        self.pause_btn.configure(state='normal')
        self.stop_btn.configure(state='normal')
        
        self.log_message(f"✅ Simulation started: {len(self.threads)} threads, {len(self.resources)} resources", 'success')
        
        # Start monitoring
        self.start_monitoring()
    
    def pause_simulation(self):
        """Pause or resume simulation"""
        if not self.simulation_running:
            return
        
        self.simulation_paused = not self.simulation_paused
        
        for thread in self.threads:
            thread.paused = self.simulation_paused
        
        status = "⏸️ PAUSED" if self.simulation_paused else "▶️ RESUMED"
        self.log_message(f"{status} simulation", 'warning' if self.simulation_paused else 'success')
        
        # Update button text
        btn_text = "▶️ Resume" if self.simulation_paused else "⏸️ Pause"
        self.pause_btn.configure(text=btn_text)
    
    def stop_simulation(self):
        """Stop the simulation"""
        if not self.simulation_running:
            return
        
        self.log_message("🛑 Stopping simulation...", 'warning')
        
        self.simulation_running = False
        
        for thread in self.threads:
            thread.running = False
        
        # Save metrics
        self.metrics.save_to_file()
        
        # Clear displays
        self.thread_tree.delete(*self.thread_tree.get_children())
        self.viz_canvas.delete('all')
        
        # Reset UI
        self.start_btn.configure(state='normal')
        self.pause_btn.configure(state='disabled', text="⏸️ Pause")
        self.stop_btn.configure(state='disabled')
        
        self.threads.clear()
        self.resources.clear()
        
        self.log_message("✅ Simulation stopped and metrics saved", 'success')
    
    def start_monitoring(self):
        """Start the monitoring loop for deadlock detection"""
        if not self.simulation_running:
            return
        
        try:
            # Detect deadlocks
            cycle = self.detector.detect_deadlock_dfs()
            
            if cycle:
                self.deadlock_flash = True
                self.log_message(f"🚨 DEADLOCK DETECTED! Cycle: {' → '.join(cycle + [cycle[0]])}", 'deadlock')
                
                if self.auto_resolve.get():
                    self.log_message("🔧 Auto-resolving deadlock...", 'warning')
                    resolution = self.resolver.resolve_deadlock(cycle, self.threads, self.resources)
                    
                    if resolution:
                        self.log_message(f"✅ Resolved using {resolution['strategy']} - Victim: {resolution['victim']}", 'success')
            
            # Update metrics
            self.metrics.update_throughput()
            
            # Check system safety periodically
            if self.update_counter % 10 == 0:
                safe, sequence = self.detector.banker_algorithm_check()
                if not safe:
                    self.log_message("⚠️ System in UNSAFE state!", 'warning')
            
            self.update_counter += 1
            
        except Exception as e:
            self.log_message(f"❌ Monitoring error: {e}", 'warning')
        
        # Schedule next check
        if self.simulation_running:
            self.root.after(2000, self.start_monitoring)  # Check every 2 seconds
    
    def start_animation_loop(self):
        """Start the main animation and update loop"""
        if self.animation_running:
            self.update_displays()
            self.root.after(500, self.start_animation_loop)  # Update every 500ms
    
    def update_displays(self):
        """Update all visual displays"""
        try:
            # Process status queue
            self.process_status_queue()
            
            # Update statistics
            if self.simulation_running:
                self.update_statistics_display()
                self.update_metrics_display()
                self.draw_resource_visualization()
            
        except Exception as e:
            logging.error(f"Display update error: {e}")
    
    def process_status_queue(self):
        """Process thread status updates"""
        while not self.status_queue.empty():
            try:
                action, data = self.status_queue.get_nowait()
                
                if action == 'update':
                    self.update_thread_display(data)
                    
            except:
                break
    
    def update_thread_display(self, data):
        """Update thread status in treeview"""
        # Find existing item
        thread_items = {}
        for item in self.thread_tree.get_children():
            values = self.thread_tree.item(item)['values']
            if values:
                thread_items[values[0]] = item
        
        # Format data
        values = (
            data['thread'],
            str(data['priority']),
            ', '.join(data['held']) if data['held'] else 'None',
            ', '.join(data['waiting']) if data['waiting'] else 'None',
            data['action'],
            data.get('efficiency', 'N/A')
        )
        
        # Update or insert
        if data['thread'] in thread_items:
            self.thread_tree.item(thread_items[data['thread']], values=values)
        else:
            item = self.thread_tree.insert('', 'end', values=values)
            
            # Color coding based on efficiency
            efficiency = data.get('efficiency', '0%')
            if isinstance(efficiency, str) and efficiency.endswith('%'):
                eff_val = float(efficiency[:-1])
                if eff_val >= 80:
                    self.thread_tree.set(item, 'Efficiency', f"✅ {efficiency}")
                elif eff_val >= 60:
                    self.thread_tree.set(item, 'Efficiency', f"⚠️ {efficiency}")
                else:
                    self.thread_tree.set(item, 'Efficiency', f"❌ {efficiency}")
    
    def update_statistics_display(self):
        """Update the statistics display"""
        if not self.metrics:
            return
        
        metrics = self.metrics.get_current_metrics()
        
        stats_text = f"""🖥️  SYSTEM STATUS
Runtime: {metrics['runtime']:.1f}s
Active Threads: {len([t for t in self.threads if t.running])}
Resources: {len(self.resources)}
Status: {'🟢 RUNNING' if not self.simulation_paused else '🟡 PAUSED'}

💀 DEADLOCKS
Total: {metrics['deadlocks']}
Frequency: {metrics['deadlock_frequency']:.1f}/hour
Avg Detection: {metrics['avg_detection_time']:.3f}s

⚡ PERFORMANCE
Requests: {metrics['total_requests']}
Success Rate: {metrics['success_rate']:.1f}%
Throughput: {metrics['throughput']:.1f}/min
Avg Wait: {metrics['avg_wait_time']:.3f}s"""
        
        self.stats_text.delete(1.0, 'end')
        self.stats_text.insert('end', stats_text)
    
    def update_metrics_display(self):
        """Update detailed performance metrics"""
        if not self.resources:
            return
        
        metrics_text = "🔧 RESOURCE UTILIZATION:\n"
        
        for resource in self.resources:
            stats = resource.get_utilization_stats()
            metrics_text += f"{resource.name:12} | {stats['utilization']:5.1f}% | "
            metrics_text += f"{stats['current_usage']:2}/{stats['total_capacity']} | "
            metrics_text += f"Queue: {stats['waiting_count']:2}\n"
        
        # Add detection efficiency if available
        if self.detector:
            det_stats = self.detector.get_detection_efficiency()
            if det_stats:
                metrics_text += f"\n🔍 DETECTION PERFORMANCE:\n"
                metrics_text += f"Avg Time: {det_stats['avg_detection_time']:.3f}s\n"
                metrics_text += f"Total Detections: {det_stats['total_detections']}\n"
        
        self.metrics_text.delete(1.0, 'end')
        self.metrics_text.insert('end', metrics_text)
    
    def draw_resource_visualization(self):
        """Draw beautiful resource allocation visualization"""
        if not self.resources or not self.threads:
            return
        
        self.viz_canvas.delete('all')
        
        canvas_width = self.viz_canvas.winfo_width()
        canvas_height = self.viz_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        # Draw resources in a circle
        center_x, center_y = canvas_width // 2, canvas_height // 2
        resource_radius = min(canvas_width, canvas_height) // 3
        
        resource_positions = {}
        
        for i, resource in enumerate(self.resources):
            angle = 2 * math.pi * i / len(self.resources)
            x = center_x + resource_radius * math.cos(angle)
            y = center_y + resource_radius * math.sin(angle)
            
            resource_positions[resource.name] = (x, y)
            
            # Draw resource node
            stats = resource.get_utilization_stats()
            color = resource.color if hasattr(resource, 'color') else self.colors['accent']
            
            # Resource circle with utilization indicator
            size = 30 + stats['utilization'] * 0.3  # Size based on utilization
            
            self.viz_canvas.create_oval(x-size//2, y-size//2, x+size//2, y+size//2,
                                       fill=color, outline='white', width=2,
                                       tags='resource')
            
            # Resource label
            self.viz_canvas.create_text(x, y-size//2-15, text=resource.name,
                                       fill='white', font=('Segoe UI', 10, 'bold'))
            
            # Utilization indicator
            util_text = f"{stats['utilization']:.0f}%"
            self.viz_canvas.create_text(x, y, text=util_text,
                                       fill='black', font=('Segoe UI', 8, 'bold'))
        
        # Draw threads around the outside
        thread_radius = resource_radius + 100
        thread_positions = {}
        
        for i, thread in enumerate(self.threads):
            if not thread.running:
                continue
                
            angle = 2 * math.pi * i / len(self.threads)
            x = center_x + thread_radius * math.cos(angle)
            y = center_y + thread_radius * math.sin(angle)
            
            thread_positions[thread.name] = (x, y)
            
            # Thread color based on priority
            if thread.priority >= 8:
                thread_color = self.colors['danger']  # High priority
            elif thread.priority >= 5:
                thread_color = self.colors['warning']  # Medium priority
            else:
                thread_color = self.colors['success']  # Low priority
            
            # Draw thread node
            self.viz_canvas.create_rectangle(x-15, y-15, x+15, y+15,
                                           fill=thread_color, outline='white', width=2,
                                           tags='thread')
            
            # Thread label
            self.viz_canvas.create_text(x, y-25, text=thread.name,
                                       fill='white', font=('Segoe UI', 9, 'bold'))
            
            # Priority indicator
            self.viz_canvas.create_text(x, y, text=str(thread.priority),
                                       fill='black', font=('Segoe UI', 8, 'bold'))
        
        # Draw allocation and waiting relationships
        for thread in self.threads:
            if not thread.running or thread.name not in thread_positions:
                continue
            
            tx, ty = thread_positions[thread.name]
            
            # Draw held resources (solid lines)
            for resource_name in thread.held_resources:
                if resource_name in resource_positions:
                    rx, ry = resource_positions[resource_name]
                    self.viz_canvas.create_line(tx, ty, rx, ry,
                                              fill=self.colors['success'], width=3,
                                              tags='allocation')
                    
                    # Arrow head for allocation
                    self.draw_arrow_head(tx, ty, rx, ry, self.colors['success'])
            
            # Draw waiting relationships (dashed lines)
            for resource_name in thread.requested_resources:
                if resource_name in resource_positions:
                    rx, ry = resource_positions[resource_name]
                    self.viz_canvas.create_line(tx, ty, rx, ry,
                                              fill=self.colors['danger'], width=2,
                                              dash=(5, 5), tags='waiting')
                    
                    # Arrow head for waiting
                    self.draw_arrow_head(tx, ty, rx, ry, self.colors['danger'])
        
        # Flash effect for deadlocks
        if self.deadlock_flash:
            self.viz_canvas.create_rectangle(0, 0, canvas_width, canvas_height,
                                           outline=self.colors['danger'], width=5,
                                           tags='flash')
            self.viz_canvas.create_text(canvas_width//2, 50, 
                                       text="🚨 DEADLOCK DETECTED! 🚨",
                                       fill=self.colors['danger'], 
                                       font=('Segoe UI', 16, 'bold'),
                                       tags='flash')
            self.root.after(1000, self.clear_flash)  # Clear flash after 1 second
    
    def draw_arrow_head(self, x1, y1, x2, y2, color):
        """Draw arrow head for directed edges"""
        # Calculate arrow head position
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        # Unit vector
        ux = dx / length
        uy = dy / length
        
        # Arrow head at 80% of the line
        ax = x1 + 0.8 * dx
        ay = y1 + 0.8 * dy
        
        # Arrow head points
        arrow_length = 10
        arrow_angle = math.pi / 6
        
        # Left point
        lx = ax - arrow_length * (ux * math.cos(arrow_angle) - uy * math.sin(arrow_angle))
        ly = ay - arrow_length * (ux * math.sin(arrow_angle) + uy * math.cos(arrow_angle))
        
        # Right point
        rx = ax - arrow_length * (ux * math.cos(-arrow_angle) - uy * math.sin(-arrow_angle))
        ry = ay - arrow_length * (ux * math.sin(-arrow_angle) + uy * math.cos(-arrow_angle))
        
        # Draw arrow head
        self.viz_canvas.create_polygon(ax, ay, lx, ly, rx, ry,
                                      fill=color, outline=color)
    
    def clear_flash(self):
        """Clear deadlock flash effect"""
        self.deadlock_flash = False
        self.viz_canvas.delete('flash')
    
    def log_message(self, message, tag='info'):
        """Add a message to the event log with styling"""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert('end', full_message, tag)
        self.log_text.see('end')
        
        # Keep log size reasonable
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > 1000:
            self.log_text.delete('1.0', '500.0')
        
        # Also log to file
        if tag == 'deadlock':
            logging.warning(message)
        elif tag == 'warning':
            logging.warning(message)
        else:
            logging.info(message)

def main():
    """Main application entry point"""
    root = tk.Tk()
    
    try:
        app = BeautifulDeadlockGUI(root)
        
        # Add window closing handler
        def on_closing():
            if app.simulation_running:
                if messagebox.askokcancel("Quit", "Simulation is running. Stop and quit?"):
                    app.stop_simulation()
                    root.destroy()
            else:
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start the GUI
        root.mainloop()
        
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Application failed to start:\n{e}")
        logging.error(f"Fatal application error: {e}")

if __name__ == "__main__":
    print("🔄 Enhanced Deadlock Detection & Resolution Simulator")
    print("🎯 Starting Beautiful GUI Interface...")
    print("📚 SCSB081 Assessment - Advanced Implementation with Modern UI")
    print("=" * 70)
    
    main()