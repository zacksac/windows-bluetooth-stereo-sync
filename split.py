import sounddevice as sd
import numpy as np
from collections import deque
import json
import tkinter as tk
from tkinter import ttk, messagebox, Menu
import os
import webbrowser

CONFIG_FILE = 'audio_splitter_config.json'
APP_VERSION = "1.0.0"
CONTACT_EMAIL = "your_email@example.com"  # <--- CHANGE THIS TO YOUR EMAIL

# ---------------- CONFIG LOAD/SAVE ----------------
def load_config():
    default_cfg = {
        "input": 0, "out1": 0, "out2": 0, 
        "delay1": 0, "delay2": 50, 
        "vol1": 1.0, "vol2": 1.0, 
        "mapping": "L1R2"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                for key, val in default_cfg.items():
                    if key not in cfg:
                        cfg[key] = val
                return cfg
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print("Failed to save config:", e)

# ---------------- DEVICE ENUMERATION ----------------
def get_filtered_devices():
    devices = sd.query_devices()
    input_list = []
    output_list = []

    for i, d in enumerate(devices):
        dev_str = f"{i}: {d['name']} (in:{d['max_input_channels']} out:{d['max_output_channels']})"
        dev_name_lower = d['name'].lower()
        
        if d['max_input_channels'] > 0 and "cable" in dev_name_lower:
            input_list.append(dev_str)
            
        if d['max_output_channels'] > 0 and "speakers" in dev_name_lower:
            output_list.append(dev_str)

    if not input_list:
        input_list = [f"{i}: {d['name']}" for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    if not output_list:
        output_list = [f"{i}: {d['name']}" for i, d in enumerate(devices) if d['max_output_channels'] > 0]

    return input_list, output_list

def extract_index(text):
    try:
        if not text: return None
        return int(text.split(':', 1)[0])
    except: return None

def find_device_in_list(target_idx, device_list):
    prefix = f"{target_idx}:"
    for item in device_list:
        if item.startswith(prefix):
            return item
    return device_list[0] if device_list else ""

# ---------------- AUDIO ENGINE ----------------
class AudioEngine:
    def __init__(self, input_idx, out1_idx, out2_idx, delay_ms1, delay_ms2, vol1, vol2, mapping):
        self.input_idx = input_idx
        self.out1_idx = out1_idx
        self.out2_idx = out2_idx
        
        self.delay_ms1 = float(delay_ms1)
        self.delay_ms2 = float(delay_ms2)
        self.vol1 = float(vol1)
        self.vol2 = float(vol2)
        self.mapping = mapping

        self.samplerate = 44100 
        self.blocksize = 1024 

        self.delay_blocks1 = self._calc_blocks(self.delay_ms1)
        self.delay_buffer1 = self._create_buffer(self.delay_blocks1)
        
        self.delay_blocks2 = self._calc_blocks(self.delay_ms2)
        self.delay_buffer2 = self._create_buffer(self.delay_blocks2)

        self.stream_in = sd.InputStream(device=self.input_idx, channels=2, samplerate=self.samplerate, blocksize=self.blocksize, callback=self.callback)
        self.stream_out1 = sd.OutputStream(device=self.out1_idx, channels=2, samplerate=self.samplerate, blocksize=self.blocksize)
        self.stream_out2 = sd.OutputStream(device=self.out2_idx, channels=2, samplerate=self.samplerate, blocksize=self.blocksize)

    def _calc_blocks(self, delay_ms):
        return max(1, int((delay_ms / 1000) * self.samplerate) // self.blocksize)

    def _create_buffer(self, num_blocks):
        silence = np.zeros((self.blocksize,), dtype=np.float32)
        return deque([silence.copy() for _ in range(num_blocks)], maxlen=num_blocks)

    def start(self):
        self.stream_out1.start()
        self.stream_out2.start()
        self.stream_in.start()

    def stop(self):
        for st in (self.stream_in, self.stream_out1, self.stream_out2):
            try: st.stop(); st.close()
            except: pass

    def update(self, d1, d2, v1, v2):
        self.delay_ms1, self.delay_ms2 = float(d1), float(d2)
        self.vol1, self.vol2 = float(v1), float(v2)

        nb1 = self._calc_blocks(self.delay_ms1)
        if nb1 != self.delay_blocks1:
            self.delay_blocks1 = nb1
            self.delay_buffer1 = self._create_buffer(nb1)

        nb2 = self._calc_blocks(self.delay_ms2)
        if nb2 != self.delay_blocks2:
            self.delay_blocks2 = nb2
            self.delay_buffer2 = self._create_buffer(nb2)

    def update_mapping(self, mapping):
        self.mapping = mapping

    def callback(self, indata, frames, time, status):
        if status: print("Status:", status)
        
        if indata.ndim < 2 or indata.shape[1] < 2:
            left_sig = right_sig = indata.flatten()
        else:
            left_sig = indata[:, 0]
            right_sig = indata[:, 1]

        if self.mapping == 'L1R2':
            s1_sig = left_sig * self.vol1
            s2_sig = right_sig * self.vol2
        else:
            s1_sig = right_sig * self.vol1
            s2_sig = left_sig * self.vol2
            
        self.delay_buffer1.append(s1_sig.copy())
        self.delay_buffer2.append(s2_sig.copy())

        out1 = np.column_stack((self.delay_buffer1[0], self.delay_buffer1[0]))
        out2 = np.column_stack((self.delay_buffer2[0], self.delay_buffer2[0]))

        try:
            self.stream_out1.write(out1)
            self.stream_out2.write(out2)
        except Exception: pass

# ---------------- GUI APPLICATION ----------------
class SplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth Audio Router")
        self.root.geometry("750x620")
        
        try:
            style = ttk.Style()
            style.theme_use('clam')
        except: pass

        self.cfg = load_config()
        self.engine = None
        
        # 1. SETUP MENU
        self.create_menu()

        # 2. CHECK DRIVER
        self.check_driver_status()
        
        self.setup_ui()
        self.refresh_device_list()

    def create_menu(self):
        """Creates the top menu bar"""
        menubar = Menu(self.root)
        
        # Help Menu
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="Version Info", command=self.show_version)
        help_menu.add_separator()
        help_menu.add_command(label="Contact Support", command=self.show_contact)
        
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def show_version(self):
        messagebox.showinfo(
            "Version Info", 
            f"Bluetooth Audio Router\nVersion: {APP_VERSION}\n\n"
            "Built with Python & SoundDevice\n"
            "Audio Engine: Real-time Low Latency"
        )

    def show_contact(self):
        msg = f"Developer Contact:\n{CONTACT_EMAIL}\n\nDo you want to send an email now?"
        if messagebox.askyesno("Contact Info", msg):
            webbrowser.open(f"mailto:{CONTACT_EMAIL}")

    def check_driver_status(self):
        try:
            devices = sd.query_devices()
            cable_found = any("cable" in d['name'].lower() for d in devices)
            
            if not cable_found:
                response = messagebox.askyesno(
                    "Driver Missing", 
                    "⚠️ VB-Cable Virtual Driver is not detected!\n\n"
                    "This app requires the free VB-Cable driver to work.\n"
                    "Do you want to open the download page now?"
                )
                if response:
                    webbrowser.open("https://vb-audio.com/Cable/")
        except Exception: pass

    def setup_ui(self):
        # -- Variables --
        self.input_var = tk.StringVar()
        self.out1_var = tk.StringVar()
        self.out2_var = tk.StringVar()
        self.mapping_var = tk.StringVar(value=self.cfg.get("mapping", "L1R2"))

        self.spk1_header = tk.StringVar(value="Speaker 1 Controls")
        self.spk2_header = tk.StringVar(value="Speaker 2 Controls")

        self.out1_var.trace_add("write", self.update_header_labels)
        self.out2_var.trace_add("write", self.update_header_labels)

        # -- UI Layout --
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill='both', expand=True)

        dev_frame = ttk.LabelFrame(main_frame, text="Device Configuration", padding="10")
        dev_frame.pack(fill='x', pady=(0, 10))
        dev_frame.columnconfigure(1, weight=1)
        
        ttk.Label(dev_frame, text="Input Source:").grid(row=0, column=0, sticky='w', pady=5)
        self.combo_in = ttk.Combobox(dev_frame, textvariable=self.input_var, state="readonly")
        self.combo_in.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(dev_frame, text="Speaker 1 Output:").grid(row=1, column=0, sticky='w', pady=5)
        self.combo_out1 = ttk.Combobox(dev_frame, textvariable=self.out1_var, state="readonly")
        self.combo_out1.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(dev_frame, text="Speaker 2 Output:").grid(row=2, column=0, sticky='w', pady=5)
        self.combo_out2 = ttk.Combobox(dev_frame, textvariable=self.out2_var, state="readonly")
        self.combo_out2.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        self.btn_refresh = ttk.Button(dev_frame, text="🔄 Refresh Device List", command=self.refresh_device_list)
        self.btn_refresh.grid(row=3, column=1, sticky='e', padx=10, pady=5)

        map_frame = ttk.LabelFrame(main_frame, text="Channel Routing", padding="10")
        map_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Radiobutton(map_frame, text="Normal (L → Spk1, R → Spk2)", variable=self.mapping_var, value='L1R2', command=self.on_live_update).pack(side='left', padx=20)
        ttk.Radiobutton(map_frame, text="Swapped (R → Spk1, L → Spk2)", variable=self.mapping_var, value='R1L2', command=self.on_live_update).pack(side='left', padx=20)

        controls_frame = ttk.LabelFrame(main_frame, text="Audio Calibration", padding="10")
        controls_frame.pack(fill='both', expand=True, pady=(0, 10))

        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)

        # Speaker 1
        spk1_frame = ttk.Frame(controls_frame)
        spk1_frame.grid(row=0, column=0, sticky='nsew', padx=10)
        ttk.Label(spk1_frame, textvariable=self.spk1_header, font=('Helvetica', 9, 'bold'), wraplength=300).pack(pady=5)
        
        ttk.Label(spk1_frame, text="Added Delay (ms)").pack(anchor='w')
        self.s1_delay = tk.Scale(spk1_frame, from_=0, to=2000, orient="horizontal", command=self.on_live_update)
        self.s1_delay.set(self.cfg.get("delay1", 0))
        self.s1_delay.pack(fill='x', pady=(0, 15))

        ttk.Label(spk1_frame, text="Volume").pack(anchor='w')
        self.s1_vol = tk.Scale(spk1_frame, from_=0, to=1, resolution=0.01, orient="horizontal", command=self.on_live_update)
        self.s1_vol.set(self.cfg.get("vol1", 1.0))
        self.s1_vol.pack(fill='x')

        ttk.Separator(controls_frame, orient='vertical').grid(row=0, column=0, sticky='ens', padx=0)

        # Speaker 2
        spk2_frame = ttk.Frame(controls_frame)
        spk2_frame.grid(row=0, column=1, sticky='nsew', padx=10)
        ttk.Label(spk2_frame, textvariable=self.spk2_header, font=('Helvetica', 9, 'bold'), wraplength=300).pack(pady=5)

        ttk.Label(spk2_frame, text="Added Delay (ms)").pack(anchor='w')
        self.s2_delay = tk.Scale(spk2_frame, from_=0, to=2000, orient="horizontal", command=self.on_live_update)
        self.s2_delay.set(self.cfg.get("delay2", 50))
        self.s2_delay.pack(fill='x', pady=(0, 15))

        ttk.Label(spk2_frame, text="Volume").pack(anchor='w')
        self.s2_vol = tk.Scale(spk2_frame, from_=0, to=1, resolution=0.01, orient="horizontal", command=self.on_live_update)
        self.s2_vol.set(self.cfg.get("vol2", 1.0))
        self.s2_vol.pack(fill='x')

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x', pady=10)
        
        self.lbl_status = ttk.Label(action_frame, text="Status: Ready", font=('Helvetica', 10))
        self.lbl_status.pack(side='left', padx=5)

        self.btn_stop = ttk.Button(action_frame, text="STOP", command=self.stop_audio, state='disabled')
        self.btn_stop.pack(side='right', padx=5)

        self.btn_start = ttk.Button(action_frame, text="START ENGINE", command=self.start_audio)
        self.btn_start.pack(side='right', padx=5)

    def update_header_labels(self, *args):
        def clean_name(val, default_name):
            if not val or ":" not in val: return default_name
            parts = val.split(':', 1)
            if len(parts) > 1:
                name = parts[1].split('(')[0].strip()
                return f"{name} CONTROLS"
            return default_name

        self.spk1_header.set(clean_name(self.out1_var.get(), "SPEAKER 1 CONTROLS"))
        self.spk2_header.set(clean_name(self.out2_var.get(), "SPEAKER 2 CONTROLS"))

    def refresh_device_list(self):
        in_list, out_list = get_filtered_devices()
        self.combo_in['values'] = in_list
        self.combo_out1['values'] = out_list
        self.combo_out2['values'] = out_list
        self.input_var.set(find_device_in_list(self.cfg.get("input", 0), in_list))
        self.out1_var.set(find_device_in_list(self.cfg.get("out1", 0), out_list))
        self.out2_var.set(find_device_in_list(self.cfg.get("out2", 0), out_list))
        self.update_header_labels()

    def on_live_update(self, *args):
        if self.engine:
            self.engine.update(self.s1_delay.get(), self.s2_delay.get(), self.s1_vol.get(), self.s2_vol.get())
            self.engine.update_mapping(self.mapping_var.get())

    def start_audio(self):
        if self.engine: self.stop_audio()
        i = extract_index(self.input_var.get())
        o1 = extract_index(self.out1_var.get())
        o2 = extract_index(self.out2_var.get())

        if i is None or o1 is None or o2 is None:
            messagebox.showerror("Selection Error", "Please ensure all devices are selected.")
            return

        try:
            self.engine = AudioEngine(i, o1, o2, self.s1_delay.get(), self.s2_delay.get(), self.s1_vol.get(), self.s2_vol.get(), self.mapping_var.get())
            self.engine.start()
            save_config({
                "input": i, "out1": o1, "out2": o2,
                "delay1": self.s1_delay.get(), "delay2": self.s2_delay.get(),
                "vol1": self.s1_vol.get(), "vol2": self.s2_vol.get(),
                "mapping": self.mapping_var.get()
            })
            self.lbl_status.config(text="Status: RUNNING", foreground="green")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.btn_refresh.config(state="disabled")
            self.combo_in.config(state="disabled")
            self.combo_out1.config(state="disabled")
            self.combo_out2.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Audio Error", str(e))
            self.lbl_status.config(text=f"Error: {str(e)[:20]}...", foreground="red")

    def stop_audio(self):
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.lbl_status.config(text="Status: STOPPED", foreground="black")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_refresh.config(state="normal")
        self.combo_in.config(state="readonly")
        self.combo_out1.config(state="readonly")
        self.combo_out2.config(state="readonly")

if __name__ == "__main__":
    root = tk.Tk()
    app = SplitterApp(root)
    root.mainloop()