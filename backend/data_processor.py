import json
import time
import datetime


# ... (DP_SPECS, interpret_fault_bitmap) ...
DP_SPECS = {
    "total_forward_energy": {"name": "正向总有功电量 (Total Forward Energy)", "type": "Integer", "scale": 100,
                             "unit": "kWh"},
    "phase_a": {"name": "A相电压，电流及功率 (Phase A V/C/P)", "type": "Raw",
                "description": "Packed hex data, requires specific parsing docs."},
    "fault": {"name": "故障告警 (Fault Alarm)", "type": "Bitmap",
              "labels": ["short_circuit_alarm", "surge_alarm", "overload_alarm", "leakagecurr_alarm", "temp_dif_fault",
                         "fire_alarm", "high_power_alarm", "self_test_alarm", "ov_cr", "unbalance_alarm", "ov_vol",
                         "undervoltage_alarm", "miss_phase_alarm", "outage_alarm", "magnetism_alarm", "credit_alarm",
                         "no_balance_alarm"]},
    "switch_prepayment": {"name": "预付费功能开关 (Prepayment Switch)", "type": "Boolean"},
    "clear_energy": {"name": "剩余可用电量清零 (Clear Remaining Energy)", "type": "Boolean"},
    "balance_energy": {"name": "剩余可用电量显示 (Remaining 可用电量显示)", "type": "Integer", "scale": 1,
                       "unit": "kWh"},
    "charge_energy": {"name": "电量充值 (Charge Energy)", "type": "Integer", "scale": 1, "unit": "kWh"},
    "leakage_current": {"name": "剩余电流显示 (Leakage Current)", "type": "Integer", "scale": 1, "unit": "mA"},
    "switch": {"name": "断路器开关 (Breaker Switch)", "type": "Boolean"},
    "alarm_set_1": {"name": "告警设置1 (Alarm Setting 1)", "type": "Raw"},
    "alarm_set_2": {"name": "告警设置2 (Alarm Setting 2)", "type": "Raw"},
    "breaker_id": {"name": "设备号显示 (Device Breaker ID)", "type": "String"},
    "leakagecurr_test": {"name": "剩余电流测试 (Leakage Current Test)", "type": "Boolean"},
    "power_factor": {"name": "功率因素 (Power Factor)", "type": "Integer", "scale": 1000},
    "supply_frequency": {"name": "供电频率 (供电频率)", "type": "Integer", "scale": 10, "unit": "Hz"},
    "output_voltage": {"name": "Voltage", "type": "Integer", "scale": 10, "unit": "V"},
    "output_current": {"name": "Current", "type": "Integer", "scale": 1000, "unit": "A"},
    "output_power": {"name": "有功功率 (Active Power)", "type": "Integer", "scale": 1000, "unit": "kW"},
    "refresh": {"name": "刷新上报 (Refresh Report)", "type": "Boolean"},
    "clr_all_energy": {"name": "清电量 (Clear All Energy)", "type": "Boolean"}
}


def interpret_fault_bitmap(value, labels):
    if not isinstance(value, int):
        return f"Unknown fault value type: {value}"
    active_alarms = []
    for i, label in enumerate(labels):
        if (value >> i) & 1:
            active_alarms.append(label)
    if not active_alarms:
        return "No active faults"
    return ", ".join(active_alarms)



_last_known_device_state = {
    "switch": "N/A",
    "output_voltage": "N/A",
    "supply_frequency": "N/A",
    "output_current": "N/A",
    "output_power": "N/A",
    "power_factor": "N/A",
}


_last_actual_data_timestamp = None


_last_gs_snapshot_sent = {}



def initialize_dp_state():
    global _last_known_device_state, _last_gs_snapshot_sent, _last_actual_data_timestamp
    _last_known_device_state = {
        "switch": "N/A",
        "output_voltage": "N/A",
        "supply_frequency": "N/A",
        "output_current": "N/A",
        "output_power": "N/A",
        "power_factor": "N/A",
    }
    _last_gs_snapshot_sent = {}
    _last_actual_data_timestamp = None



def get_offline_snapshot(device_id, timestamp):
    global _last_known_device_state, _last_actual_data_timestamp


    _last_known_device_state["switch"] = "OFF"
    _last_known_device_state["output_voltage"] = 0.0
    _last_known_device_state["supply_frequency"] = 0.0
    _last_known_device_state["output_current"] = 0.0
    _last_known_device_state["output_power"] = 0.0
    _last_known_device_state["power_factor"] = 0.0

    _last_actual_data_timestamp = None


    snapshot_data = {
        "timestamp": timestamp,
        "time_12hr": time.strftime('%I:%M:%S %p', time.localtime()),
        "device_id": device_id,
        "dp_code_raw": [],

        "Breaker Switch": "OFF",
        "Voltage (V)": 0.0,
        "Frequency (Hz)": 0.0,
        "Current (A)": 0.0,
        "Active Power (kW)": 0.0,
        "Power Factor": 0.0,
    }

    individual_dp_records = [
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "switch", "dp_name": "Breaker Switch",
         "dp_value_display": "OFF", "dp_value_save": "OFF", "dp_unit": "", "dp_type": "Boolean"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "output_voltage", "dp_name": "Voltage",
         "dp_value_display": "0.0 V", "dp_value_save": 0.0, "dp_unit": "V", "dp_type": "Integer"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "supply_frequency", "dp_name": "Frequency",
         "dp_value_display": "0.0 Hz", "dp_value_save": 0.0, "dp_unit": "Hz", "dp_type": "Integer"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "output_current", "dp_name": "Current",
         "dp_value_display": "0.0 A", "dp_value_save": 0.0, "dp_unit": "A", "dp_type": "Integer"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "output_power", "dp_name": "Active Power",
         "dp_value_display": "0.0 kW", "dp_value_save": 0.0, "dp_unit": "kW", "dp_type": "Integer"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "power_factor", "dp_name": "Power Factor",
         "dp_value_display": "0.0", "dp_value_save": 0.0, "dp_unit": "", "dp_type": "Integer"},
        {"timestamp": timestamp, "device_id": device_id, "dp_code": "device_status", "dp_name": "Device Status",
         "dp_value_display": "OFFLINE", "dp_value_save": "OFFLINE", "dp_unit": "", "dp_type": "String"},
    ]
    return snapshot_data, individual_dp_records


def process_device_data_snapshot(device_id, raw_dp_list, timestamp):
    global _last_known_device_state, _last_actual_data_timestamp

    individual_dp_records = []


    if raw_dp_list:
        _last_actual_data_timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')


    for dp_change in raw_dp_list:
        dp_code = dp_change.get('code')
        dp_value_raw = dp_change.get('value')

        dp_info = DP_SPECS.get(dp_code)

        if dp_info:
            dp_name = dp_info["name"]
            dp_type = dp_info["type"]
            dp_scale = dp_info.get("scale", 1)
            dp_unit = dp_info.get("unit", "")

            value_for_state = dp_value_raw
            display_value_individual = dp_value_raw

            if dp_type == "Integer":
                value_for_state = round(dp_value_raw / dp_scale, 3)
                display_value_individual = f"{value_for_state} {dp_unit}"
            elif dp_type == "Boolean":
                value_for_state = "ON" if dp_value_raw else "OFF"
                display_value_individual = value_for_state
            elif dp_type == "Bitmap":
                value_for_state = interpret_fault_bitmap(dp_value_raw, dp_info.get("labels", []))
                display_value_individual = value_for_state
            elif dp_type == "Raw":
                value_for_state = dp_value_raw
                display_value_individual = f"{dp_value_raw} (Raw Data)"
            else:
                value_for_state = dp_value_raw
                display_value_individual = str(dp_value_raw)

            if dp_code in _last_known_device_state:
                _last_known_device_state[dp_code] = value_for_state

            individual_dp_records.append({
                "timestamp": timestamp, "device_id": device_id, "dp_code": dp_code,
                "dp_name": dp_name, "dp_value_display": display_value_individual,
                "dp_value_save": value_for_state, "dp_unit": dp_unit, "dp_type": dp_type
            })
        else:
            individual_dp_records.append({
                "timestamp": timestamp, "device_id": device_id, "dp_code": dp_code,
                "dp_name": "Unknown DP", "dp_value_display": dp_value_raw,
                "dp_value_save": dp_value_raw, "dp_unit": "", "dp_type": "Unknown"
            })


    snapshot_data = {
        "timestamp": timestamp,
        "time_12hr": time.strftime('%I:%M:%S %p', time.localtime()),
        "device_id": device_id,
        "dp_code_raw": raw_dp_list,

        "Breaker Switch": _last_known_device_state.get("switch", "N/A"),
        "Voltage (V)": _last_known_device_state.get("output_voltage", "N/A"),
        "Frequency (Hz)": _last_known_device_state.get("supply_frequency", "N/A"),
        "Current (A)": _last_known_device_state.get("output_current", "N/A"),
        "Active Power (kW)": _last_known_device_state.get("output_power", "N/A"),
        "Power Factor": _last_known_device_state.get("power_factor", "N/A"),
    }


    if snapshot_data["Breaker Switch"] == "OFF":
        if snapshot_data["Voltage (V)"] != "N/A": snapshot_data["Voltage (V)"] = 0.0
        if snapshot_data["Frequency (Hz)"] != "N/A": snapshot_data["Frequency (Hz)"] = 0.0
        if snapshot_data["Current (A)"] != "N/A": snapshot_data["Current (A)"] = 0.0
        if snapshot_data["Active Power (kW)"] != "N/A": snapshot_data["Active Power (kW)"] = 0.0
        if snapshot_data["Power Factor"] != "N/A": snapshot_data["Power Factor"] = 0.0

    return snapshot_data, individual_dp_records



def print_clean_snapshot(snapshot_data):
    print(f"  Time: {snapshot_data['time_12hr']}")
    print(
        f"  Breaker Switch: {snapshot_data['Breaker Switch'] if snapshot_data['Breaker Switch'] is not None else 'N/A'}")
    print(f"  Voltage: {snapshot_data['Voltage (V)'] if snapshot_data['Voltage (V)'] is not None else 'N/A'} V")
    print(
        f"  Frequency: {snapshot_data['Frequency (Hz)'] if snapshot_data['Frequency (Hz)'] is not None else 'N/A'} Hz")
    print(f"  Current: {snapshot_data['Current (A)'] if snapshot_data['Current (A)'] is not None else 'N/A'} A")
    print(
        f"  Active Power: {snapshot_data['Active Power (kW)'] if snapshot_data['Active Power (kW)'] is not None else 'N/A'} kW")
    print(f"  Power Factor: {snapshot_data['Power Factor'] if snapshot_data['Power Factor'] is not None else 'N/A'}")