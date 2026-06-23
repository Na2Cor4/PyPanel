from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psutil


@dataclass
class _LhmSensors:
    cpu_freq: Any = None
    cpu_power: Any = None
    cpu_temp: Any = None


class PanelStats:
    def __init__(self) -> None:
        self._computer = None
        self._cpu_hardware: list[Any] = []
        self._lhm = _LhmSensors()
        self._nvml = None
        self._gpu_handle = None

        psutil.cpu_percent(interval=None)
        self._init_lhm()
        self._init_nvml()

    def close(self) -> None:
        if self._computer is not None:
            try:
                self._computer.Close()
            except Exception as exc:
                print(f"HardwareMonitor close failed: {exc}")

        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception as exc:
                print(f"NVML shutdown failed: {exc}")

    def read_all(self) -> dict:
        cpu_usage = self._read_cpu_usage()

        if (
            self._lhm.cpu_freq is not None
            or self._lhm.cpu_power is not None
            or self._lhm.cpu_temp is not None
        ):
            self._update_lhm_cpu()
        cpu_freq = self._read_cpu_freq()
        cpu_power = self._read_cpu_power()
        cpu_temp = self._read_cpu_temp()

        gpu_usage = self._read_gpu_usage()
        gpu_power = self._read_gpu_power()
        gpu_temp = self._read_gpu_temp()
        gpu_memory = self._read_gpu_memory()

        ram = self._read_ram()

        return {
            "cpu_usage_percent": cpu_usage,
            "cpu_freq_ghz": cpu_freq,
            "cpu_power_w": cpu_power,
            "cpu_temp_c": cpu_temp,
            "gpu_usage_percent": gpu_usage,
            "gpu_power_w": gpu_power,
            "gpu_temp_c": gpu_temp,
            "gpu_memory_used_mb": self._gpu_memory_used_mb(gpu_memory),
            "gpu_memory_total_mb": self._gpu_memory_total_mb(gpu_memory),
            "ram_used_gb": self._ram_used_gb(ram),
            "ram_total_gb": self._ram_total_gb(ram),
            "ram_percent": self._ram_percent(ram),
        }

    def print_cpu_sensors(self) -> None:
        if self._computer is None:
            print("HardwareMonitor is not available.")
            return

        self._update_lhm_cpu()
        for hardware in self._cpu_hardware:
            self._print_hardware_sensors(hardware)
            for sub in hardware.SubHardware:
                self._print_hardware_sensors(sub)

    def _init_lhm(self) -> None:
        try:
            from HardwareMonitor.Util import OpenComputer

            self._computer = OpenComputer(
                cpu=True,
                gpu=False,
                memory=False,
                motherboard=False,
                storage=False,
                network=False,
            )
        except Exception as exc:
            print(f"HardwareMonitor init failed: {exc}")
            self._computer = None
            return

        try:
            for hardware in self._computer.Hardware:
                hardware.Update()
                if self._is_cpu_hardware(hardware):
                    self._cpu_hardware.append(hardware)
                for sub in hardware.SubHardware:
                    sub.Update()
                    if self._is_cpu_hardware(sub):
                        self._cpu_hardware.append(sub)

            self._discover_lhm_sensors()
        except Exception as exc:
            print(f"HardwareMonitor sensor discovery failed: {exc}")

    def _init_nvml(self) -> None:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as exc:
            print(f"NVML init failed: {exc}")
            self._nvml = None
            self._gpu_handle = None

    def _discover_lhm_sensors(self) -> None:
        overall_freq = None
        first_core_freq = None
        package_power = None
        fallback_power = None
        temp_candidates: list[tuple[int, Any]] = []

        for hardware in self._cpu_hardware:
            for target in [hardware, *hardware.SubHardware]:
                for sensor in target.Sensors:
                    sensor_type = str(sensor.SensorType).lower()
                    name = str(sensor.Name).lower()

                    if sensor_type == "clock":
                        if self._is_overall_cpu_clock(name) and overall_freq is None:
                            overall_freq = sensor
                        elif "core" in name and first_core_freq is None:
                            first_core_freq = sensor

                    if sensor_type == "power":
                        if "package" in name and package_power is None:
                            package_power = sensor
                        elif fallback_power is None:
                            fallback_power = sensor

                    if sensor_type == "temperature":
                        priority = self._cpu_temp_priority(name)
                        temp_candidates.append((priority, sensor))

        self._lhm.cpu_freq = overall_freq or first_core_freq
        self._lhm.cpu_power = package_power or fallback_power
        if temp_candidates:
            temp_candidates.sort(key=lambda item: item[0])
            self._lhm.cpu_temp = temp_candidates[0][1]

    def _update_lhm_cpu(self) -> None:
        for hardware in self._cpu_hardware:
            try:
                hardware.Update()
                for sub in hardware.SubHardware:
                    sub.Update()
            except Exception as exc:
                print(f"HardwareMonitor update failed: {exc}")

    def _read_cpu_usage(self) -> float | None:
        try:
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return None

    def _read_cpu_freq(self) -> float | None:
        if self._lhm.cpu_freq is None:
            return None
        return self._sensor_value(self._lhm.cpu_freq, scale=1 / 1000)

    def _read_cpu_power(self) -> float | None:
        if self._lhm.cpu_power is None:
            return None
        return self._sensor_value(self._lhm.cpu_power)

    def _read_cpu_temp(self) -> float | None:
        if self._lhm.cpu_temp is None:
            return None
        return self._sensor_value(self._lhm.cpu_temp)

    def _read_gpu_usage(self) -> float | None:
        if self._nvml is None or self._gpu_handle is None:
            return None
        try:
            return float(self._nvml.nvmlDeviceGetUtilizationRates(self._gpu_handle).gpu)
        except Exception:
            return None

    def _read_gpu_power(self) -> float | None:
        if self._nvml is None or self._gpu_handle is None:
            return None
        try:
            return float(self._nvml.nvmlDeviceGetPowerUsage(self._gpu_handle)) / 1000.0
        except Exception:
            return None

    def _read_gpu_temp(self) -> float | None:
        if self._nvml is None or self._gpu_handle is None:
            return None
        try:
            return float(
                self._nvml.nvmlDeviceGetTemperature(
                    self._gpu_handle,
                    self._nvml.NVML_TEMPERATURE_GPU,
                )
            )
        except Exception:
            return None

    def _gpu_memory_used_mb(self, memory: Any | None) -> float | None:
        if memory is None:
            return None
        try:
            return float(memory.used) / 1024 / 1024
        except Exception:
            return None

    def _gpu_memory_total_mb(self, memory: Any | None) -> float | None:
        if memory is None:
            return None
        try:
            return float(memory.total) / 1024 / 1024
        except Exception:
            return None

    def _read_gpu_memory(self) -> Any | None:
        if self._nvml is None or self._gpu_handle is None:
            return None
        try:
            return self._nvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
        except Exception:
            return None

    def _read_ram(self) -> Any | None:
        try:
            return psutil.virtual_memory()
        except Exception:
            return None

    @staticmethod
    def _ram_used_gb(ram: Any | None) -> float | None:
        if ram is None:
            return None
        try:
            return float(ram.used) / 1024**3
        except Exception:
            return None

    @staticmethod
    def _ram_total_gb(ram: Any | None) -> float | None:
        if ram is None:
            return None
        try:
            return float(ram.total) / 1024**3
        except Exception:
            return None

    @staticmethod
    def _ram_percent(ram: Any | None) -> float | None:
        if ram is None:
            return None
        try:
            return float(ram.percent)
        except Exception:
            return None

    @staticmethod
    def _sensor_value(sensor: Any, scale: float = 1.0) -> float | None:
        try:
            value = sensor.Value
        except Exception:
            return None

        if value is None:
            return None
        try:
            return float(value) * scale
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_cpu_hardware(hardware: Any) -> bool:
        return "cpu" in str(hardware.HardwareType).lower()

    @staticmethod
    def _is_overall_cpu_clock(name: str) -> bool:
        return (
            "total" in name
            or "average" in name
            or "package" in name
            or name in {"cpu clock", "cpu clocks"}
        )

    @staticmethod
    def _cpu_temp_priority(name: str) -> int:
        if "cpu package" in name or name == "package":
            return 0
        if "core max" in name:
            return 1
        if "tctl/tdie" in name or ("tctl" in name and "tdie" in name):
            return 2
        if "ccd" in name:
            return 3
        return 4

    @staticmethod
    def _print_hardware_sensors(hardware: Any) -> None:
        print(f"[{hardware.HardwareType}] {hardware.Name}")
        for sensor in hardware.Sensors:
            sensor_type = str(sensor.SensorType)
            if sensor_type.lower() in {"clock", "power", "temperature"}:
                value = getattr(sensor, "Value", None)
                print(f"  {sensor_type:8s} {sensor.Name}: {value}")
