import time

from HardwareMonitor.Util import OpenComputer


class PanelStats:
    def __init__(self):
        self.computer = OpenComputer(
            cpu=True,
            gpu=True,
            memory=True,
            motherboard=False,
            storage=False,
            network=True,
        )

        self.hardware_list = []
        self.sensors = {
            "cpu_usage_percent": None,
            "cpu_power_w": None,
            "gpu_usage_percent": None,
            "gpu_power_w": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
            "ram_percent": None,
            "ram_used_gb": None,
            "ram_available_gb": None,
            "net_upload": None,
            "net_download": None,
        }

        self.cpu_clock_sensors = []

        self._discover()

    def close(self):
        self.computer.Close()

    def _update_all_hardware(self):
        for hardware in self.hardware_list:
            hardware.Update()

            for sub in hardware.SubHardware:
                sub.Update()

    def _discover(self):
        # 先更新一次，让传感器列表完整出现
        for hardware in self.computer.Hardware:
            hardware.Update()
            self.hardware_list.append(hardware)

            for sub in hardware.SubHardware:
                sub.Update()

        for hardware in self.hardware_list:
            self._scan_hardware(hardware)

            for sub in hardware.SubHardware:
                self._scan_hardware(sub)

    def _scan_hardware(self, hardware):
        hw_type = str(hardware.HardwareType).lower()

        is_cpu = "cpu" in hw_type
        is_gpu = "gpu" in hw_type
        is_memory = "memory" in hw_type or "ram" in hw_type
        is_network = "network" in hw_type

        for sensor in hardware.Sensors:
            sensor_type = str(sensor.SensorType).lower()
            name = str(sensor.Name).lower()

            # ---------------- CPU ----------------

            if is_cpu and sensor_type == "load":
                if "total" in name:
                    self.sensors["cpu_usage_percent"] = sensor

            if is_cpu and sensor_type == "clock":
                if "core" in name:
                    self.cpu_clock_sensors.append(sensor)

            if is_cpu and sensor_type == "power":
                if "package" in name:
                    self.sensors["cpu_power_w"] = sensor

            # ---------------- GPU ----------------

            if is_gpu and sensor_type == "load":
                if "core" in name or name == "gpu core":
                    self.sensors["gpu_usage_percent"] = sensor

            if is_gpu and sensor_type == "power":
                if (
                    "package" in name
                    or "total" in name
                    or "graphics" in name
                    or "gpu power" in name
                ):
                    self.sensors["gpu_power_w"] = sensor

            if is_gpu and sensor_type in ("data", "smalldata"):
                if "memory used" in name:
                    self.sensors["gpu_memory_used_mb"] = sensor
                elif "memory total" in name:
                    self.sensors["gpu_memory_total_mb"] = sensor

            # ---------------- RAM ----------------

            if is_memory and sensor_type == "load":
                if "memory" in name:
                    self.sensors["ram_percent"] = sensor

            if is_memory and sensor_type == "data":
                if "used" in name:
                    self.sensors["ram_used_gb"] = sensor
                elif "available" in name:
                    self.sensors["ram_available_gb"] = sensor

            # ---------------- Network ----------------

            if is_network and sensor_type == "throughput":
                if "upload" in name or "send" in name:
                    self.sensors["net_upload"] = sensor
                elif "download" in name or "receive" in name:
                    self.sensors["net_download"] = sensor

    def _value(self, key):
        sensor = self.sensors.get(key)
        if sensor is None:
            return None

        value = sensor.Value
        if value is None:
            return None

        return float(value)

    def read_all(self):
        self._update_all_hardware()

        cpu_usage = self._value("cpu_usage_percent")
        cpu_power = self._value("cpu_power_w")

        gpu_usage = self._value("gpu_usage_percent")
        gpu_power = self._value("gpu_power_w")
        gpu_mem_used = self._value("gpu_memory_used_mb")
        gpu_mem_total = self._value("gpu_memory_total_mb")

        ram_percent = self._value("ram_percent")
        ram_used = self._value("ram_used_gb")
        ram_available = self._value("ram_available_gb")

        net_upload_raw = self._value("net_upload")
        net_download_raw = self._value("net_download")

        # CPU 平均频率
        cpu_freq_ghz = None
        clock_values = []

        for sensor in self.cpu_clock_sensors:
            value = sensor.Value
            if value is not None:
                clock_values.append(float(value))

        if clock_values:
            cpu_freq_ghz = sum(clock_values) / len(clock_values) / 1000

        # RAM total
        ram_total = None
        if ram_used is not None and ram_available is not None:
            ram_total = ram_used + ram_available

        # LibreHardwareMonitor 的 Throughput 通常是 bytes/s
        net_upload_mb_s = None
        net_download_mb_s = None

        if net_upload_raw is not None:
            net_upload_mb_s = net_upload_raw / 1024 / 1024

        if net_download_raw is not None:
            net_download_mb_s = net_download_raw / 1024 / 1024

        return {
            "cpu_usage_percent": cpu_usage,
            "cpu_freq_ghz": cpu_freq_ghz,
            "cpu_power_w": cpu_power,
            "gpu_usage_percent": gpu_usage,
            "gpu_power_w": gpu_power,
            "gpu_memory_used_mb": gpu_mem_used,
            "gpu_memory_total_mb": gpu_mem_total,
            "ram_used_gb": ram_used,
            "ram_total_gb": ram_total,
            "ram_percent": ram_percent,
            "net_upload_mb_s": net_upload_mb_s,
            "net_download_mb_s": net_download_mb_s,
        }


def fmt(value, unit="", digits=1):
    if value is None:
        return "---"
    return f"{value:.{digits}f}{unit}"


if __name__ == "__main__":
    stats = PanelStats()

    try:
        while True:
            d = stats.read_all()

            print(
                f"CPU {fmt(d['cpu_usage_percent'], '%')} | "
                f"{fmt(d['cpu_freq_ghz'], 'G', 2)} | "
                f"{fmt(d['cpu_power_w'], 'W')} || "
                f"GPU {fmt(d['gpu_usage_percent'], '%')} | "
                f"{fmt(d['gpu_power_w'], 'W')} | "
                f"VRAM {fmt(d['gpu_memory_used_mb'], 'MB', 0)} / "
                f"{fmt(d['gpu_memory_total_mb'], 'MB', 0)} || "
                f"RAM {fmt(d['ram_used_gb'], 'G')} / "
                f"{fmt(d['ram_total_gb'], 'G')} | "
                f"{fmt(d['ram_percent'], '%')} || "
                f"NET ↑{fmt(d['net_upload_mb_s'], 'MB/s', 2)} "
                f"↓{fmt(d['net_download_mb_s'], 'MB/s', 2)}"
            )

            time.sleep(1.5)

    finally:
        stats.close()
